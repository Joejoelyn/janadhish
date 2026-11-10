from __future__ import annotations

import os
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


TEMP_DIR = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = f"sqlite:///{Path(TEMP_DIR.name, 'storefront-test.db').as_posix()}"
os.environ['SECRET_KEY'] = secrets.token_hex(32)

from backend.database import Base, SessionLocal, engine  # noqa: E402
from backend.auth import get_current_user, login_throttle_key  # noqa: E402
from backend.main import app, seed_initial_data  # noqa: E402
from backend.models import ContactMessage, ContactUpdate, CustomRequest, Design, Fabric, FulfillmentEvent, LoginThrottle, Order, PaymentRefund, PaymentReview, Product, User  # noqa: E402


class StorefrontApiTests(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.client = TestClient(app)
        self.client.__enter__()
        self.product = self.client.get('/api/products').json()[0]

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)

    def order_payload(self, **item_overrides: object) -> dict:
        item = {
            'product_id': self.product['id'],
            'quantity': 1,
            'size': self.product['sizes'][0],
            'color': self.product['colors'][0],
            'with_pads': False,
        }
        item.update(item_overrides)
        return {
            'customer_name': 'Test Shopper',
            'email': 'shopper@example.com',
            'shipping_address': 'Test address',
            'city': 'Udaipur',
            'state': 'Rajasthan',
            'postal_code': '313001',
            'country': 'India',
            'payment_method': 'upi_qr',
            'checkout_key': secrets.token_urlsafe(24),
            'cart_items': [item],
        }

    def admin_headers(self, email: str) -> dict[str, str]:
        response = self.client.post('/api/auth/login', json={
            'email': email, 'password': 'strong-password-123',
        })
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': f"Bearer {response.json()['access_token']}"}

    def test_guest_order_uses_server_price_and_reserves_stock(self) -> None:
        expected = self.product['without_pads_price']
        payload = self.order_payload()
        payload['cart_items'][0]['unit_price'] = 1
        response = self.client.post('/api/orders', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], expected + (0 if expected >= 3000 else 250))
        with SessionLocal() as db:
            product = db.get(Product, self.product['id'])
            order = db.get(Order, response.json()['order_id'])
            self.assertEqual(product.stock_quantity, 7)
            self.assertIsNone(order.user_id)
            self.assertEqual(order.items[0].unit_price, expected)

    def test_saved_cart_validates_options_and_uses_current_price_and_shipping(self) -> None:
        self.assertEqual(self.client.get('/api/cart').status_code, 401)
        with SessionLocal() as db:
            user = User(full_name='Cart Shopper', email='cart@example.com', hashed_password='')
            db.add(user)
            db.commit()
            user_id = user.id
        app.dependency_overrides[get_current_user] = lambda: User(id=user_id)
        try:
            item = {
                'product_id': self.product['id'], 'quantity': 1,
                'size': self.product['sizes'][0], 'color': self.product['colors'][0],
            }
            self.assertEqual(self.client.post('/api/cart', json={**item, 'size': 'wrong'}).status_code, 400)
            self.assertEqual(self.client.post('/api/cart', json={**item, 'quantity': 101}).status_code, 422)
            added = self.client.post('/api/cart', json=item)
            self.assertEqual(added.status_code, 200, added.text)
            cart = self.client.get('/api/cart').json()
            price = self.product['without_pads_price']
            self.assertEqual(cart['items'][0]['unit_price'], price)
            self.assertEqual(cart['shipping'], 0 if price >= 3000 else 250)
            self.assertEqual(cart['total'], price + cart['shipping'])
            with SessionLocal() as db:
                product = db.get(Product, self.product['id'])
                product.sale_price = 777.0
                db.commit()
            updated = self.client.get('/api/cart').json()
            self.assertEqual(updated['items'][0]['unit_price'], 777.0)
            self.assertEqual(updated['total'], 1027.0)
            self.assertEqual(self.client.post('/api/cart', json={**item, 'quantity': 100}).status_code, 409)
        finally:
            del app.dependency_overrides[get_current_user]

    def test_checkout_conflict_recovers_existing_order_without_reserving_stock_twice(self) -> None:
        payload = self.order_payload()
        first = self.client.post('/api/orders', json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        repeat = self.client.post('/api/orders', json=payload)
        self.assertEqual(repeat.status_code, 200, repeat.text)
        self.assertEqual(repeat.json()['order_id'], first.json()['order_id'])
        changed = {**payload, 'shipping_address': 'A different test address'}
        self.assertEqual(self.client.post('/api/orders', json=changed).status_code, 409)
        recovered = self.client.post('/api/orders/recover', json={'checkout_key': payload['checkout_key']})
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()['order_id'], first.json()['order_id'])
        self.assertEqual(recovered.json()['checkout_token'], first.json()['checkout_token'])
        self.assertIsNone(recovered.json()['review_note'])
        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 1)
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 7)
        self.assertEqual(self.client.post('/api/orders/recover', json={
            'checkout_key': secrets.token_urlsafe(24),
        }).status_code, 404)

    def test_payment_responses_are_not_cached(self) -> None:
        order = self.client.post('/api/orders', json=self.order_payload())
        self.assertEqual(order.status_code, 200, order.text)
        self.assertEqual(order.headers.get('Cache-Control'), 'no-store')
        token = order.json()['checkout_token']
        payment = self.client.get(f'/api/payments/{token}')
        self.assertEqual(payment.status_code, 200, payment.text)
        self.assertEqual(payment.headers.get('Cache-Control'), 'no-store')
        private_status = self.client.post('/api/payments/status', json={'checkout_token': token})
        self.assertEqual(private_status.status_code, 200, private_status.text)
        self.assertEqual(private_status.json()['order_id'], order.json()['order_id'])
        self.assertEqual(private_status.headers.get('Cache-Control'), 'no-store')
        self.assertIsNone(self.client.get('/api/products').headers.get('Cache-Control'))

    def test_public_routes_return_correct_status_and_indexing_headers(self) -> None:
        self.assertEqual(self.client.get('/admin/catalog').status_code, 200)
        self.assertEqual(self.client.get('/admin/fulfillment').status_code, 200)
        self.assertEqual(
            self.client.get('/admin/catalog').headers['X-Robots-Tag'], 'noindex, nofollow',
        )
        self.assertEqual(self.client.get('/missing-page').status_code, 404)
        self.assertEqual(self.client.get('/product/not-a-number').status_code, 422)
        self.assertEqual(self.client.get('/product/999999').status_code, 404)
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        self.assertIn('Disallow: /checkout', robots.text)
        self.assertIn('/sitemap.xml', robots.text)

    def test_product_metadata_and_sitemap_reflect_active_catalog(self) -> None:
        with SessionLocal() as db:
            product = db.get(Product, self.product['id'])
            product.name = 'Kurti "Summer" <new>'
            product.short_description = 'Light <silk> & cotton'
            db.commit()
        response = self.client.get(f"/product/{self.product['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertIn('Kurti &quot;Summer&quot; &lt;new&gt; | JANADHISH', response.text)
        self.assertIn('Light &lt;silk&gt; &amp; cotton', response.text)
        self.assertNotIn('<new>', response.text)
        self.assertIn('rel="canonical"', response.text)
        sitemap = self.client.get('/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn(f"/product/{self.product['id']}</loc>", sitemap.text)
        with SessionLocal() as db:
            product = db.get(Product, self.product['id'])
            product.is_active = False
            db.commit()
        self.assertEqual(self.client.get(f"/product/{self.product['id']}").status_code, 404)
        self.assertNotIn(
            f"/product/{self.product['id']}</loc>", self.client.get('/sitemap.xml').text,
        )

    def test_storefront_media_urls_resolve(self) -> None:
        products = self.client.get('/api/products').json()
        fabrics = self.client.get('/api/fabrics').json()
        designs = self.client.get('/api/designs').json()
        paths = {
            '/Images/logo/logo.png',
            '/Images/products/white-halter-neck-kurti/photo-01.png',
            '/Images/products/green-farshi-salwar-set/photo-39.png',
            '/Images/products/semi-chanderi-farshi-salwar-set/photo-44.png',
            '/assets/images/payments/janadhish-upi.jpeg',
        }
        product_paths = {path for product in products for path in
                         [product['image_url'], *product['gallery']] if path}
        self.assertTrue(product_paths)
        self.assertTrue(all(path.endswith('.webp') for path in product_paths))
        paths.update(product_paths)
        paths.update(item['image_url'] for item in [*fabrics, *designs] if item['image_url'])
        for path in sorted(paths):
            with self.subTest(path=path):
                response = self.client.head(path)
                self.assertEqual(response.status_code, 200)
                if path in product_paths:
                    self.assertEqual(response.headers['content-type'], 'image/webp')

    def test_catalog_price_changes_match_checkout_and_survive_seed(self) -> None:
        with SessionLocal() as db:
            product = db.get(Product, self.product['id'])
            product.price = 2500
            product.sale_price = 2000
            db.commit()
        listing = self.client.get('/api/products').json()
        changed = next(item for item in listing if item['id'] == self.product['id'])
        self.assertEqual(changed['without_pads_price'], 2000)
        self.assertEqual(changed['with_pads_price'], 2500)
        response = self.client.post('/api/orders', json=self.order_payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], 2250)
        padded = self.client.post('/api/orders', json=self.order_payload(with_pads=True))
        self.assertEqual(padded.status_code, 200, padded.text)
        self.assertEqual(padded.json()['total'], 2750)
        seed_initial_data()
        with SessionLocal() as db:
            product = db.get(Product, self.product['id'])
            self.assertEqual(product.price, 2500)
            self.assertEqual(product.sale_price, 2000)
            self.assertEqual(product.stock_quantity, 6)

    def test_admin_catalog_edits_are_authorized_and_audited(self) -> None:
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Catalog Manager', 'email': 'catalog@example.com', 'password': 'strong-password-123',
        }).json()
        headers = {'Authorization': f"Bearer {registration['access_token']}"}
        product_id = self.product['id']
        self.assertEqual(self.client.get('/api/admin/products').status_code, 401)
        self.assertEqual(self.client.get('/api/admin/products', headers=headers).status_code, 403)
        with SessionLocal() as db:
            db.get(User, registration['user']['id']).is_admin = True
            db.commit()
        self.assertEqual(self.client.get('/api/admin/products', headers=headers).status_code, 403)
        headers = self.admin_headers('catalog@example.com')
        edit = {
            'name': self.product['name'], 'short_description': self.product['short_description'],
            'description': self.product['description'], 'fabric_details': self.product['fabric_details'],
            'care_instructions': self.product['care_instructions'],
            'without_pads_price': 2000, 'with_pads_price': 2500,
            'stock_quantity': 5, 'expected_stock_quantity': 8,
            'is_new_arrival': True, 'is_best_seller': False,
            'is_featured': False, 'is_active': True,
        }
        self.assertEqual(self.client.put(f'/api/admin/products/{product_id}', json=edit).status_code, 401)
        self.assertEqual(self.client.put(f'/api/admin/products/{product_id}', json=edit, headers=headers).status_code, 200)
        invalid = {**edit, 'with_pads_price': 1900}
        self.assertEqual(self.client.put(f'/api/admin/products/{product_id}', json=invalid, headers=headers).status_code, 422)
        invalid = {**edit, 'stock_quantity': -1}
        self.assertEqual(self.client.put(f'/api/admin/products/{product_id}', json=invalid, headers=headers).status_code, 422)
        history = self.client.get(f'/api/admin/products/{product_id}/history', headers=headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()), 1)
        self.assertEqual(history.json()[0]['after']['stock_quantity'], 5)
        listing = self.client.get('/api/products').json()
        self.assertEqual(next(item for item in listing if item['id'] == product_id)['without_pads_price'], 2000)
        created = self.client.post('/api/orders', json=self.order_payload())
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()['total'], 2250)
        stale = self.client.put(f'/api/admin/products/{product_id}', json={**edit, 'stock_quantity': 3}, headers=headers)
        self.assertEqual(stale.status_code, 409, stale.text)
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, product_id).stock_quantity, 4)
        fresh = self.client.put(f'/api/admin/products/{product_id}', json={
            **edit, 'expected_stock_quantity': 4, 'stock_quantity': 3,
        }, headers=headers)
        self.assertEqual(fresh.status_code, 200, fresh.text)
        self.assertEqual(fresh.json()['stock_quantity'], 3)
        with SessionLocal() as db:
            db.get(User, registration['user']['id']).is_admin = False
            db.commit()
        self.assertEqual(self.client.get('/api/admin/products', headers=headers).status_code, 403)

    def test_bad_quantity_and_insufficient_stock_do_not_create_order(self) -> None:
        self.assertEqual(self.client.post('/api/orders', json=self.order_payload(quantity=0)).status_code, 422)
        self.assertEqual(self.client.post('/api/orders', json=self.order_payload(quantity=101)).status_code, 422)
        self.assertEqual(self.client.post('/api/orders', json=self.order_payload(quantity=9)).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 0)
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)

    def test_checkout_requires_current_size_and_color_choices(self) -> None:
        for item_options in ({'size': None}, {'color': None}, {'size': 'Unavailable'}, {'color': 'Unavailable'}):
            response = self.client.post('/api/orders', json=self.order_payload(**item_options))
            self.assertEqual(response.status_code, 400, response.text)
        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 0)
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)

    def test_product_measurements_are_complete_and_valid_at_checkout(self) -> None:
        labels = (
            ('Bust / chest', 'Top waist', 'Hip', 'Shoulder', 'Sleeve length',
             'Kurta length', 'Trouser waist', 'Trouser hip', 'Inseam')
            if self.product['category']['slug'] == 'farshi-sets' else
            ('Bust / chest', 'Waist', 'Hip', 'Shoulder', 'Sleeve length', 'Garment length')
        )
        values = {label: 30.0 for label in labels}
        for details in (
            {'unit': 'inches', 'values': {key: value for key, value in values.items() if key != labels[0]}},
            {'unit': 'yards', 'values': values},
            {'unit': 'inches', 'values': {**values, labels[0]: -1}},
            {'unit': 'inches', 'values': {**values, labels[0]: '30'}},
            {'unit': 'inches', 'values': values, 'unexpected': True},
        ):
            response = self.client.post('/api/orders', json=self.order_payload(customization_details=details))
            self.assertEqual(response.status_code, 400, response.text)
        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 0)
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)
        accepted = self.client.post('/api/orders', json=self.order_payload(customization_details={
            'unit': 'inches', 'values': values,
        }))
        self.assertEqual(accepted.status_code, 200, accepted.text)
        with SessionLocal() as db:
            saved = db.get(Order, accepted.json()['order_id'])
            self.assertIn('Bust / chest', saved.items[0].customization_details)

    def test_checkout_rejects_addresses_outside_supported_region(self) -> None:
        for changes in ({'country': 'United States'}, {'state': 'Unknown'}):
            payload = self.order_payload()
            payload.update(changes)
            response = self.client.post('/api/orders', json=payload)
            self.assertEqual(response.status_code, 422, response.text)
        with SessionLocal() as db:
            self.assertEqual(db.query(Order).count(), 0)
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)

    def test_pads_price_and_signed_in_order_history(self) -> None:
        product = next(item for item in self.client.get('/api/products').json() if item['with_pads_price'])
        self.product = product
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Test Shopper', 'email': 'shopper@example.com', 'password': 'strong-password-123',
        })
        self.assertEqual(registration.status_code, 200, registration.text)
        token = registration.json()['access_token']
        response = self.client.post('/api/orders', json=self.order_payload(with_pads=True), headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], product['with_pads_price'] + (0 if product['with_pads_price'] >= 3000 else 250))
        history = self.client.get('/api/orders/my-orders', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]['id'], response.json()['order_id'])
        self.assertTrue(history.json()[0]['items'][0]['customization_details']['with_pads'])

    def test_signed_tokens_require_subject_and_expiry(self) -> None:
        from datetime import datetime, timedelta, timezone
        import jwt
        from backend.auth import ALGORITHM, SECRET_KEY

        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Test Shopper', 'email': 'shopper@example.com', 'password': 'strong-password-123',
        })
        self.assertEqual(registration.status_code, 200, registration.text)
        user_id = str(registration.json()['user']['id'])
        future = datetime.now(timezone.utc) + timedelta(minutes=5)
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        for claims in ({'sub': user_id}, {'exp': future}, {'sub': user_id, 'exp': past}):
            token = jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)
            response = self.client.get('/api/orders/my-orders', headers={'Authorization': f'Bearer {token}'})
            self.assertEqual(response.status_code, 401, response.text)
        valid = registration.json()['access_token']
        self.assertEqual(self.client.get('/api/orders/my-orders', headers={
            'Authorization': f'Bearer {valid}',
        }).status_code, 200)

    def test_only_order_owner_can_resume_an_open_payment(self) -> None:
        owner = self.client.post('/api/auth/register', json={
            'full_name': 'Order Owner', 'email': 'owner@example.com', 'password': 'strong-password-123',
        }).json()['access_token']
        other = self.client.post('/api/auth/register', json={
            'full_name': 'Other Shopper', 'email': 'other@example.com', 'password': 'strong-password-123',
        }).json()['access_token']
        payload = self.order_payload()
        payload['email'] = 'owner@example.com'
        order = self.client.post('/api/orders', json=payload, headers={
            'Authorization': f'Bearer {owner}',
        })
        self.assertEqual(order.status_code, 200, order.text)
        owner_history = self.client.get('/api/orders/my-orders', headers={'Authorization': f'Bearer {owner}'})
        self.assertEqual(owner_history.status_code, 200, owner_history.text)
        self.assertEqual(owner_history.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(owner_history.json()[0]['payment_token'], order.json()['checkout_token'])
        other_history = self.client.get('/api/orders/my-orders', headers={'Authorization': f'Bearer {other}'})
        self.assertEqual(other_history.json(), [])
        self.assertEqual(self.client.get('/api/orders/my-orders').status_code, 401)
        cancel = self.client.post(f"/api/payments/{order.json()['checkout_token']}/cancel")
        self.assertEqual(cancel.status_code, 200, cancel.text)
        self.assertEqual(cancel.json()['status'], 'cancellation_requested')
        open_history = self.client.get('/api/orders/my-orders', headers={'Authorization': f'Bearer {owner}'})
        self.assertEqual(open_history.json()[0]['payment_token'], order.json()['checkout_token'])

    def test_sign_in_attempts_are_limited_and_success_clears_the_counter(self) -> None:
        for _ in range(10):
            attempt = self.client.post('/api/auth/login', json={
                'email': 'missing@example.com', 'password': 'wrong-password-123',
            })
            self.assertEqual(attempt.status_code, 401, attempt.text)
        limited = self.client.post('/api/auth/login', json={
            'email': 'missing@example.com', 'password': 'wrong-password-123',
        })
        self.assertEqual(limited.status_code, 429, limited.text)
        self.assertGreater(int(limited.headers['Retry-After']), 0)

        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Login Shopper', 'email': 'login@example.com', 'password': 'strong-password-123',
        })
        self.assertEqual(registration.status_code, 200, registration.text)
        duplicate = self.client.post('/api/auth/register', json={
            'full_name': 'Login Shopper', 'email': 'login@example.com', 'password': 'strong-password-123',
        })
        self.assertEqual(duplicate.status_code, 400, duplicate.text)
        for _ in range(2):
            self.assertEqual(self.client.post('/api/auth/login', json={
                'email': 'login@example.com', 'password': 'wrong-password-123',
            }).status_code, 401)
        login = self.client.post('/api/auth/login', json={
            'email': 'login@example.com', 'password': 'strong-password-123',
        })
        self.assertEqual(login.status_code, 200, login.text)
        with SessionLocal() as db:
            self.assertIsNone(db.get(LoginThrottle, login_throttle_key('login@example.com')))

    def test_guest_contact_and_custom_request(self) -> None:
        contact = self.client.post('/api/contact', json={'name': 'Test Shopper', 'email': 'shopper@example.com', 'message': 'Question'})
        self.assertEqual(contact.status_code, 200, contact.text)
        self.assertEqual(contact.json()['ticket_number'], 'JD-000001')
        tracking = self.client.post('/api/contact/status', json={'tracking_token': contact.json()['tracking_token']})
        self.assertEqual(tracking.status_code, 200, tracking.text)
        self.assertEqual(tracking.json()['status'], 'received')
        self.assertEqual(tracking.json()['updates'], [])
        self.assertNotIn('email', tracking.json())
        self.assertEqual(self.client.post('/api/contact/status', json={'tracking_token': 'invalid-tracking-token'}).status_code, 404)
        custom = self.client.post('/api/customizations', json={
            'garment_category': 'Kurta', 'fabric_name': 'Cotton Silk', 'design_name': 'Aari Work',
            'contact_name': 'Test Shopper', 'contact_email': 'shopper@example.com',
            'measurements': {'Chest': 36, 'Waist': 30, 'Hips': 38, 'Shoulder': 14,
                             'Sleeve length': 20, 'Kurta length': 42},
            'estimated_price': 1,
        })
        self.assertEqual(custom.status_code, 200, custom.text)
        self.assertEqual(custom.json()['status'], 'pending')
        self.assertEqual(custom.json()['estimated_price'], 0)
        with SessionLocal() as db:
            saved = db.get(CustomRequest, custom.json()['id'])
            self.assertEqual(saved.preferences['contact']['email'], 'shopper@example.com')
            self.assertEqual(saved.measurements['Kurta length'], 42)
        incomplete = self.client.post('/api/customizations', json={
            'garment_category': 'Saree', 'fabric_name': 'Cotton Silk', 'design_name': 'Aari Work',
            'measurements': {'Waist': 30},
        })
        self.assertEqual(incomplete.status_code, 400)
        invalid_fabric = self.client.post('/api/customizations', json={
            'garment_category': 'Saree', 'fabric_name': 'Unknown', 'design_name': 'Aari Work',
            'contact_name': 'Test Shopper', 'contact_email': 'shopper@example.com',
            'measurements': {'Waist': 30, 'Hips': 38, 'Shoulder to waist': 16,
                             'Saree length': 65, 'Pallu length': 72},
        })
        self.assertEqual(invalid_fabric.status_code, 400)

    def test_contact_and_custom_requests_report_database_failure(self) -> None:
        from unittest.mock import patch

        from sqlalchemy.exc import SQLAlchemyError

        with patch('sqlalchemy.orm.Session.commit', side_effect=SQLAlchemyError('storage unavailable')), \
                patch('backend.routes.contact.logger.exception'), \
                patch('backend.routes.customizations.logger.exception'):
            contact = self.client.post('/api/contact', json={
                'name': 'Test Shopper', 'email': 'shopper@example.com', 'message': 'Question',
            })
            custom = self.client.post('/api/customizations', json={
                'garment_category': 'Kurta', 'fabric_name': 'Cotton Silk', 'design_name': 'Aari Work',
                'contact_name': 'Test Shopper', 'contact_email': 'shopper@example.com',
                'measurements': {'Chest': 36, 'Waist': 30, 'Hips': 38, 'Shoulder': 14,
                                 'Sleeve length': 20, 'Kurta length': 42},
            })
        self.assertEqual(contact.status_code, 503, contact.text)
        self.assertEqual(custom.status_code, 503, custom.text)
        with SessionLocal() as db:
            self.assertEqual(db.query(ContactMessage).count(), 0)
            self.assertEqual(db.query(CustomRequest).count(), 0)

    def test_required_form_text_is_trimmed_and_rejects_whitespace_only(self) -> None:
        self.assertEqual(self.client.post('/api/auth/register', json={
            'full_name': '   ', 'email': 'blank@example.com', 'password': 'strong-password-123',
        }).status_code, 422)
        self.assertEqual(self.client.post('/api/auth/register', json={
            'full_name': 'Test Shopper', 'email': 'phone@example.com',
            'phone': '1' * 51, 'password': 'strong-password-123',
        }).status_code, 422)
        self.assertEqual(self.client.post('/api/contact', json={
            'name': 'Test Shopper', 'email': 'shopper@example.com', 'message': '     ',
        }).status_code, 422)
        self.assertEqual(self.client.post('/api/customizations', json={
            'garment_category': 'Kurta', 'fabric_name': 'Cotton Silk', 'design_name': 'Aari Work',
            'contact_name': '   ', 'contact_email': 'shopper@example.com',
        }).status_code, 422)
        invalid_order = self.order_payload()
        invalid_order['customer_name'] = '   '
        self.assertEqual(self.client.post('/api/orders', json=invalid_order).status_code, 422)
        valid_order = self.order_payload()
        valid_order['customer_name'] = '  Test Shopper  '
        valid_order['city'] = '  Udaipur  '
        result = self.client.post('/api/orders', json=valid_order)
        self.assertEqual(result.status_code, 200, result.text)
        with SessionLocal() as db:
            order = db.get(Order, result.json()['order_id'])
            self.assertEqual(order.customer_name, 'Test Shopper')
            self.assertEqual(order.city, 'Udaipur')

    def test_custom_choices_follow_active_database_records(self) -> None:
        fabrics = self.client.get('/api/fabrics').json()
        designs = self.client.get('/api/designs').json()
        self.assertGreaterEqual(len(fabrics), 6)
        self.assertGreaterEqual(len(designs), 3)
        with SessionLocal() as db:
            db.get(Fabric, fabrics[0]['id']).is_active = False
            db.get(Design, designs[0]['id']).is_active = False
            db.commit()
        self.assertNotIn(fabrics[0]['id'], [item['id'] for item in self.client.get('/api/fabrics').json()])
        self.assertNotIn(designs[0]['id'], [item['id'] for item in self.client.get('/api/designs').json()])

    def test_admin_inbox_shows_customer_requests_and_messages(self) -> None:
        contact = self.client.post('/api/contact', json={
            'name': 'Test Shopper', 'email': 'shopper@example.com', 'message': 'Please call me',
        })
        self.assertEqual(contact.status_code, 200, contact.text)
        request = self.client.post('/api/customizations', json={
            'garment_category': 'Saree', 'fabric_name': 'Cotton Silk', 'design_name': 'Aari Work',
            'contact_name': 'Test Shopper', 'contact_email': 'shopper@example.com',
            'measurements': {'Waist': 30, 'Hips': 38, 'Shoulder to waist': 16,
                             'Saree length': 65, 'Pallu length': 72},
        })
        self.assertEqual(request.status_code, 200, request.text)
        self.assertEqual(self.client.get('/api/admin/custom-requests').status_code, 401)
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        headers = {'Authorization': f"Bearer {registration['access_token']}"}
        self.assertEqual(self.client.get('/api/admin/custom-requests', headers=headers).status_code, 403)
        with SessionLocal() as db:
            db.get(User, registration['user']['id']).is_admin = True
            db.commit()
        self.assertEqual(self.client.get('/api/admin/custom-requests', headers=headers).status_code, 403)
        headers = self.admin_headers('reviewer@example.com')
        inbox = self.client.get('/api/admin/custom-requests', headers=headers)
        self.assertEqual(inbox.status_code, 200, inbox.text)
        self.assertEqual(inbox.json()['items'][0]['preferences']['contact']['email'], 'shopper@example.com')
        messages = self.client.get('/api/admin/contact-messages', headers=headers)
        self.assertEqual(messages.status_code, 200, messages.text)
        self.assertEqual(messages.json()['items'][0]['message'], 'Please call me')
        self.assertEqual(messages.json()['items'][0]['status'], 'received')
        contact_url = '/api/admin/contact-messages/1/review'
        self.assertEqual(self.client.post(contact_url, json={'status': 'resolved', 'reply': 'We will call you.'}).status_code, 401)
        self.assertEqual(self.client.post(contact_url, json={'status': 'resolved', 'reply': '   '}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post(contact_url, json={'status': 'resolved', 'reply': 'x' * 2001}, headers=headers).status_code, 422)
        first_reply = self.client.post(contact_url, json={
            'status': 'in_progress', 'reply': '  We are checking your request.  ',
        }, headers=headers)
        self.assertEqual(first_reply.status_code, 200, first_reply.text)
        contact_review = self.client.post(contact_url, json={
            'status': 'resolved', 'reply': 'Please call our studio to discuss the fit.',
        }, headers=headers)
        self.assertEqual(contact_review.status_code, 200, contact_review.text)
        customer_tracking = self.client.post('/api/contact/status', json={
            'tracking_token': contact.json()['tracking_token'],
        }).json()
        self.assertEqual(customer_tracking['status'], 'resolved')
        self.assertEqual([item['reply'] for item in customer_tracking['updates']], [
            'We are checking your request.', 'Please call our studio to discuss the fit.',
        ])
        self.assertNotIn('email', customer_tracking)
        self.assertNotIn('reviewer_user_id', customer_tracking['updates'][0])
        history = self.client.get('/api/admin/contact-messages', headers=headers).json()['items'][0]['updates']
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['reviewer_user_id'], registration['user']['id'])
        with SessionLocal() as db:
            self.assertEqual(db.query(ContactUpdate).filter_by(contact_id=1).count(), 2)
        review = self.client.post(f"/api/admin/custom-requests/{request.json()['id']}/review", json={
            'status': 'reviewed', 'note': 'Contacted customer',
        }, headers=headers)
        self.assertEqual(review.status_code, 200, review.text)
        self.assertEqual(review.json()['status'], 'reviewed')
        with SessionLocal() as db:
            saved = db.get(CustomRequest, request.json()['id'])
            self.assertEqual(saved.preferences['admin_note'], 'Contacted customer')

    def test_qr_reference_requires_statement_review(self) -> None:
        payload = self.order_payload()
        created = self.client.post('/api/orders', json=payload)
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()['status'], 'awaiting_payment')
        self.assertEqual(self.client.post('/api/orders', json=payload).json()['order_id'], created.json()['order_id'])
        token = created.json()['checkout_token']
        submitted = self.client.post('/api/payments/submit', json={
            'checkout_token': token, 'reference': '123456789012', 'payer_name': 'Test Shopper',
        })
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['status'], 'payment_submitted')
        self.assertEqual(self.client.post('/api/payments/status', json={'checkout_token': token}).json()['status'], 'payment_submitted')
        self.assertEqual(self.client.get('/api/admin/payments').status_code, 401)
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        })
        reviewer_id = registration.json()['user']['id']
        with SessionLocal() as db:
            db.get(User, reviewer_id).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        self.assertEqual(self.client.post(f"/api/admin/payments/{created.json()['order_id']}/review", json={
            'decision': 'approve', 'statement_reference': '123456789012', 'statement_amount_paise': 1,
            'statement_checked': True,
        }, headers=headers).status_code, 400)
        self.assertEqual(self.client.post(f"/api/admin/payments/{created.json()['order_id']}/review", json={
            'decision': 'approve', 'statement_reference': '123456789012',
            'statement_amount_paise': round(created.json()['total'] * 100),
        }, headers=headers).status_code, 400)
        approved = self.client.post(f"/api/admin/payments/{created.json()['order_id']}/review", json={
            'decision': 'approve', 'statement_reference': '123456789012',
            'statement_amount_paise': round(created.json()['total'] * 100),
            'statement_checked': True,
        }, headers=headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()['status'], 'paid')
        closed = self.client.get('/api/admin/payments', params={'view': 'closed'}, headers=headers)
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()['items'][0]['order_id'], created.json()['order_id'])
        self.assertEqual(closed.json()['items'][0]['reviews'][0]['decision'], 'approve')
        self.assertEqual(closed.json()['items'][0]['reviews'][0]['reference'], '123456789012')
        self.assertEqual(self.client.post(f"/api/admin/payments/{created.json()['order_id']}/review", json={
            'decision': 'approve', 'statement_reference': '123456789012',
            'statement_amount_paise': round(created.json()['total'] * 100),
        }, headers=headers).status_code, 409)

    def test_completed_refund_is_audited_and_capped_at_verified_amount(self) -> None:
        payload = self.order_payload()
        created = self.client.post('/api/orders', json=payload).json()
        order_id = created['order_id']
        token = created['checkout_token']
        amount = round(created['total'] * 100)
        url = f'/api/admin/payments/{order_id}/refunds'
        refund = {
            'amount_paise': 10000, 'outgoing_reference': 'REFUND123456',
            'reason': 'Customer return approved', 'transfer_confirmed': True,
        }
        self.assertEqual(self.client.post(url, json=refund).status_code, 401)
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com',
            'password': 'strong-password-123',
        })
        with SessionLocal() as db:
            db.get(User, registration.json()['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        self.assertEqual(self.client.post(url, json=refund, headers=headers).status_code, 409)
        submitted = self.client.post('/api/payments/submit', json={
            'checkout_token': token, 'reference': '123456789012', 'payer_name': 'Test Shopper',
        })
        self.assertEqual(submitted.status_code, 200, submitted.text)
        approved = self.client.post(f'/api/admin/payments/{order_id}/review', json={
            'decision': 'approve', 'statement_reference': '123456789012',
            'statement_amount_paise': amount, 'statement_checked': True,
        }, headers=headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(self.client.post(url, json={**refund, 'transfer_confirmed': False}, headers=headers).status_code, 400)
        self.assertEqual(self.client.post(url, json={**refund, 'amount_paise': amount + 1}, headers=headers).status_code, 409)
        first = self.client.post(url, json=refund, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['refunded_amount_paise'], 10000)
        self.assertEqual(self.client.post(url, json=refund, headers=headers).status_code, 409)
        final = self.client.post(url, json={**refund, 'amount_paise': amount - 10000,
                                            'outgoing_reference': 'REFUND123457'}, headers=headers)
        self.assertEqual(final.status_code, 200, final.text)
        self.assertEqual(final.json()['refunded_amount_paise'], amount)
        self.assertEqual(self.client.post(url, json={**refund, 'outgoing_reference': 'REFUND123458'}, headers=headers).status_code, 409)
        payment = self.client.post('/api/payments/status', json={'checkout_token': token}).json()
        self.assertEqual(payment['refunded_amount_paise'], amount)
        self.assertEqual(len(payment['refunds']), 2)
        recovered = self.client.post('/api/orders/recover', json={'checkout_key': payload['checkout_key']})
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()['refunded_amount_paise'], amount)
        self.assertEqual(len(recovered.json()['refunds']), 2)
        closed = self.client.get('/api/admin/payments', params={'view': 'closed'}, headers=headers).json()
        self.assertEqual(len(closed['items'][0]['refunds']), 2)
        queue = self.client.get('/api/admin/fulfillment', headers=headers).json()
        self.assertEqual(queue['items'][0]['refunded_amount_paise'], amount)
        blocked = self.client.post(f'/api/admin/fulfillment/{order_id}', json={
            'status': 'packed', 'expected_version': 0,
        }, headers=headers)
        self.assertEqual(blocked.status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.get(Order, order_id).refunded_amount_paise, amount)
            self.assertEqual(db.query(PaymentRefund).filter_by(order_id=order_id).count(), 2)

    def test_payment_queue_prioritizes_submitted_references_and_pages(self) -> None:
        orders = [self.client.post('/api/orders', json=self.order_payload()).json() for _ in range(3)]
        for order, reference in zip(orders[1:], ('123456789012', '123456789013')):
            submitted = self.client.post(f"/api/payments/{order['checkout_token']}/submit", json={
                'reference': reference, 'payer_name': 'Test Shopper',
            })
            self.assertEqual(submitted.status_code, 200, submitted.text)
        reviewer = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, reviewer['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        first = self.client.get('/api/admin/payments', params={'limit': 1}, headers=headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()['items'][0]['order_id'], orders[1]['order_id'])
        self.assertTrue(first.json()['has_more'])
        second = self.client.get('/api/admin/payments', params={'limit': 1, 'offset': 1}, headers=headers)
        self.assertEqual(second.json()['items'][0]['order_id'], orders[2]['order_id'])
        self.assertFalse(second.json()['has_more'])
        awaiting = self.client.get('/api/admin/payments', params={'view': 'awaiting'}, headers=headers)
        self.assertEqual(awaiting.json()['items'][0]['order_id'], orders[0]['order_id'])
        self.assertFalse(awaiting.json()['has_more'])
        self.assertEqual(self.client.get('/api/admin/payments', params={'view': 'unknown'}, headers=headers).status_code, 422)

    def test_paid_order_fulfillment_requires_admin_and_advances_once(self) -> None:
        from backend.routes.orders import FARSHI_MEASUREMENTS, STANDARD_MEASUREMENTS

        shopper = self.client.post('/api/auth/register', json={
            'full_name': 'Test Shopper', 'email': 'shopper@example.com', 'password': 'strong-password-123',
        }).json()
        shopper_headers = {'Authorization': f"Bearer {shopper['access_token']}"}
        labels = FARSHI_MEASUREMENTS if self.product['category']['slug'] == 'farshi-sets' else STANDARD_MEASUREMENTS
        measurements = {'unit': 'cm', 'values': {label: 30 for label in labels}}
        created = self.client.post('/api/orders', json=self.order_payload(
            customization_details=measurements,
        ), headers=shopper_headers).json()
        order_id = created['order_id']
        url = f'/api/admin/fulfillment/{order_id}'
        self.assertEqual(self.client.get('/api/admin/fulfillment').status_code, 401)
        self.assertEqual(self.client.get('/api/admin/fulfillment', headers=shopper_headers).status_code, 403)
        self.assertEqual(self.client.post(url, json={'status': 'packed', 'expected_version': 0}, headers=shopper_headers).status_code, 403)
        reviewer = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, reviewer['user']['id']).is_admin = True
            db.commit()
        admin_headers = self.admin_headers('reviewer@example.com')
        self.assertEqual(self.client.post(url, json={'status': 'packed', 'expected_version': 0}, headers=admin_headers).status_code, 409)
        self.assertEqual(self.client.get('/api/admin/fulfillment', headers=admin_headers).json()['items'], [])
        token = created['checkout_token']
        self.assertEqual(self.client.post(f'/api/payments/{token}/submit', json={
            'reference': '123456789012', 'payer_name': 'Test Shopper',
        }).status_code, 200)
        approved = self.client.post(f'/api/admin/payments/{order_id}/review', json={
            'decision': 'approve', 'statement_reference': '123456789012',
            'statement_amount_paise': round(created['total'] * 100), 'statement_checked': True,
        }, headers=admin_headers)
        self.assertEqual(approved.status_code, 200, approved.text)
        owner_history = self.client.get('/api/orders/my-orders', headers=shopper_headers).json()
        self.assertEqual(owner_history[0]['payment_token'], created['checkout_token'])
        queue = self.client.get('/api/admin/fulfillment', headers=admin_headers).json()
        self.assertEqual(queue['items'][0]['shipping_address'], 'Test address')
        self.assertEqual(queue['items'][0]['items'][0]['customization_details'], {
            'with_pads': False, 'measurements': measurements,
        })
        self.assertEqual(queue['items'][0]['fulfillment']['status'], 'processing')
        self.assertEqual(self.client.post(url, json={
            'status': 'shipped', 'expected_version': 0,
            'carrier': 'Test Carrier', 'tracking_reference': 'TRACK12345',
        }, headers=admin_headers).status_code, 409)
        packed = self.client.post(url, json={'status': 'packed', 'expected_version': 0}, headers=admin_headers)
        self.assertEqual(packed.status_code, 200, packed.text)
        self.assertEqual(self.client.post(url, json={'status': 'packed', 'expected_version': 0}, headers=admin_headers).status_code, 409)
        self.assertEqual(self.client.post(url, json={'status': 'shipped', 'expected_version': 1}, headers=admin_headers).status_code, 422)
        shipped = self.client.post(url, json={
            'status': 'shipped', 'expected_version': 1,
            'carrier': 'Test Carrier', 'tracking_reference': 'TRACK12345',
        }, headers=admin_headers)
        self.assertEqual(shipped.status_code, 200, shipped.text)
        self.assertEqual(self.client.get(f'/api/payments/{token}').json()['fulfillment']['tracking_reference'], 'TRACK12345')
        self.assertEqual(self.client.get('/api/orders/my-orders', headers=shopper_headers).json()[0]['fulfillment']['status'], 'shipped')
        delivered = self.client.post(url, json={'status': 'delivered', 'expected_version': 2}, headers=admin_headers)
        self.assertEqual(delivered.status_code, 200, delivered.text)
        self.assertEqual(delivered.json()['status'], 'delivered')
        self.assertEqual(self.client.get('/api/admin/fulfillment', headers=admin_headers).json()['items'], [])
        history = self.client.get('/api/admin/fulfillment', params={'view': 'delivered'}, headers=admin_headers)
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(history.json()['items'][0]['order_id'], order_id)
        self.assertEqual(history.json()['items'][0]['fulfillment']['status'], 'delivered')
        self.assertEqual(self.client.get('/api/admin/fulfillment', params={'view': 'unknown'}, headers=admin_headers).status_code, 422)
        self.assertEqual(self.client.post(url, json={'status': 'delivered', 'expected_version': 3}, headers=admin_headers).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual([event.status for event in db.query(FulfillmentEvent).order_by(FulfillmentEvent.id).all()], [
                'packed', 'shipped', 'delivered',
            ])

    def test_customer_cancellation_waits_for_reviewer_before_releasing_stock(self) -> None:
        created = self.client.post('/api/orders', json=self.order_payload())
        token = created.json()['checkout_token']
        self.assertEqual(self.client.post('/api/payments/cancel', json={'checkout_token': token}).json()['status'], 'cancellation_requested')
        self.assertEqual(self.client.post(f'/api/payments/{token}/cancel').json()['status'], 'cancellation_requested')
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 7)
        reviewer = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, reviewer['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        queue = self.client.get('/api/admin/payments?view=awaiting', headers=headers).json()['items']
        self.assertEqual(queue[0]['status'], 'cancellation_requested')
        url = f"/api/admin/payments/{created.json()['order_id']}/review"
        self.assertEqual(self.client.post(url, json={
            'decision': 'cancel', 'note': 'Customer request',
        }, headers=headers).status_code, 400)
        self.assertEqual(self.client.post(url, json={
            'decision': 'cancel', 'note': 'No matching deposit after statement check',
            'statement_checked_no_payment': True,
        }, headers=headers).json()['status'], 'cancelled')
        self.assertEqual(self.client.post('/api/payments/cancel', json={'checkout_token': token}).status_code, 409)
        self.assertEqual(self.client.post(f'/api/payments/{token}/submit', json={
            'reference': '123456789012', 'payer_name': 'Test Shopper',
        }).status_code, 409)
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)

    def test_late_payment_reference_reopens_cancellation_request_for_review(self) -> None:
        created = self.client.post('/api/orders', json=self.order_payload()).json()
        token = created['checkout_token']
        self.assertEqual(self.client.post('/api/payments/cancel', json={'checkout_token': token}).json()['status'], 'cancellation_requested')
        submitted = self.client.post('/api/payments/submit', json={
            'checkout_token': token, 'reference': '123456789012', 'payer_name': 'Test Shopper',
        })
        self.assertEqual(submitted.status_code, 200, submitted.text)
        self.assertEqual(submitted.json()['status'], 'payment_submitted')
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 7)
            self.assertEqual(db.get(Order, created['order_id']).status, 'payment_submitted')

    def test_reference_cannot_be_reused_for_another_order(self) -> None:
        first = self.client.post('/api/orders', json=self.order_payload()).json()
        second = self.client.post('/api/orders', json=self.order_payload()).json()
        reference = {'reference': '123456789012', 'payer_name': 'Test Shopper'}
        self.assertEqual(self.client.post(f"/api/payments/{first['checkout_token']}/submit", json=reference).status_code, 200)
        self.assertEqual(self.client.post(f"/api/payments/{second['checkout_token']}/submit", json=reference).status_code, 409)

    def test_submitted_reference_is_immutable_during_review(self) -> None:
        created = self.client.post('/api/orders', json=self.order_payload()).json()
        url = f"/api/payments/{created['checkout_token']}/submit"
        first = {'reference': '123456789012', 'payer_name': 'Test Shopper'}
        self.assertEqual(self.client.post(url, json=first).status_code, 200)
        self.assertEqual(self.client.post(url, json=first).status_code, 200)
        self.assertEqual(self.client.post(url, json={**first, 'reference': '123456789013'}).status_code, 409)
        self.assertEqual(self.client.get(f"/api/payments/{created['checkout_token']}").json()['payment_reference'], first['reference'])

    def test_rejected_reference_is_audited_and_replaced_cleanly(self) -> None:
        created = self.client.post('/api/orders', json=self.order_payload()).json()
        payment_url = f"/api/payments/{created['checkout_token']}"
        self.assertEqual(self.client.post(f'{payment_url}/submit', json={
            'reference': '123456789012', 'payer_name': 'Test Shopper',
        }).status_code, 200)
        reviewer = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, reviewer['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        rejected = self.client.post(f"/api/admin/payments/{created['order_id']}/review", json={
            'decision': 'reject', 'note': 'No matching bank entry',
        }, headers=headers)
        self.assertEqual(rejected.status_code, 200, rejected.text)
        self.assertEqual(rejected.json()['status'], 'awaiting_payment')
        self.assertIsNone(rejected.json()['payment_reference'])
        self.assertEqual(rejected.json()['review_note'], 'No matching bank entry')
        queue = self.client.get('/api/admin/payments', params={'view': 'awaiting'}, headers=headers).json()
        self.assertIsNone(queue['items'][0]['payment_reference'])
        self.assertEqual(queue['items'][0]['reviews'][0]['reference'], '123456789012')
        self.assertEqual(queue['items'][0]['reviews'][0]['decision'], 'reject')
        with SessionLocal() as db:
            self.assertEqual(db.query(PaymentReview).one().reference, '123456789012')
        self.assertEqual(self.client.post(f'{payment_url}/submit', json={
            'reference': '123456789012', 'payer_name': 'Test Shopper',
        }).status_code, 409)
        replaced = self.client.post(f'{payment_url}/submit', json={
            'reference': '123456789013', 'payer_name': 'Test Shopper',
        })
        self.assertEqual(replaced.status_code, 200, replaced.text)
        self.assertEqual(replaced.json()['payment_reference'], '123456789013')

    def test_catalog_price_filter_includes_regular_price_products(self) -> None:
        regular = next(item for item in self.client.get('/api/products').json() if item['sale_price'] is None)
        response = self.client.get('/api/products', params={'min_price': regular['price'], 'max_price': regular['price']})
        self.assertEqual(response.status_code, 200)
        self.assertIn(regular['id'], [item['id'] for item in response.json()])

    def test_stylist_uses_catalog_when_ai_service_is_unconfigured(self) -> None:
        from unittest.mock import patch

        with patch.dict(os.environ, {'GROQ_API_KEY': ''}):
            response = self.client.post('/api/ai/chat', json={'message': 'Show me a kurti'})
            blank = self.client.post('/api/ai/chat', json={'message': '   '})
            oversized = self.client.post('/api/ai/chat', json={'message': 'x' * 501})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('Kurti', response.json()['response'])
        self.assertEqual(blank.status_code, 422)
        self.assertEqual(oversized.status_code, 422)

    def test_stylist_uses_relevant_products_and_verified_policy_answers(self) -> None:
        from unittest.mock import patch

        from backend.routes.ai_assistant import product_summary
        from backend.services.pricing import product_variant_prices

        with SessionLocal() as db:
            products = db.query(Product).filter(Product.is_active.is_(True)).all()
            target = next(product for product in products if product.name == 'Bell Sleeve Kurti')
            standard, with_pads = product_variant_prices(target)
            summary = product_summary('Bell Sleeve Kurti', products)
        self.assertTrue(summary.startswith('- Bell Sleeve Kurti:'), summary)
        self.assertIn(f'standard INR {standard:g}', summary)
        self.assertIn(f'with pads INR {with_pads:g}', summary)

        with patch('backend.routes.ai_assistant.os.getenv', return_value='enabled'), \
                patch('backend.routes.ai_assistant.get_groq_reply') as remote_reply:
            response = self.client.post('/api/ai/chat', json={'message': 'Shipping and returns?'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('Standard shipping', response.json()['response'])
        self.assertIn('return and refund policy', response.json()['response'])
        remote_reply.assert_not_called()

    def test_stylist_requires_opt_in_before_external_ai_request(self) -> None:
        from unittest.mock import patch

        with patch('backend.routes.ai_assistant.os.getenv', return_value='enabled'), \
                patch('backend.routes.ai_assistant.get_groq_reply', return_value='AI reply') as remote_reply:
            local = self.client.post('/api/ai/chat', json={'message': 'Show me a kurti'})
            self.assertEqual(local.status_code, 200, local.text)
            self.assertIn('Kurti', local.json()['response'])
            remote_reply.assert_not_called()
            opted_in = self.client.post('/api/ai/chat', json={
                'message': 'Show me a kurti', 'allow_external_ai': True,
            })
            self.assertEqual(opted_in.status_code, 200, opted_in.text)
            self.assertEqual(opted_in.json()['response'], 'AI reply')
            remote_reply.assert_called_once()

    def test_only_qr_payment_and_reviewer_cannot_cancel_unchecked_submission(self) -> None:
        payload = self.order_payload()
        payload['payment_method'] = 'cod'
        self.assertEqual(self.client.post('/api/orders', json=payload).status_code, 422)
        payload['payment_method'] = 'upi_qr'
        created = self.client.post('/api/orders', json=payload).json()
        self.client.post(f"/api/payments/{created['checkout_token']}/submit", json={
            'reference': '123456789012', 'payer_name': 'Test Shopper',
        })
        registration = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, registration['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        response = self.client.post(f"/api/admin/payments/{created['order_id']}/review", json={
            'decision': 'cancel', 'note': 'No payment found',
        }, headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(f"/api/payments/{created['checkout_token']}").json()['status'], 'payment_submitted')

    def test_reviewer_cannot_cancel_unsubmitted_order_without_account_check(self) -> None:
        created = self.client.post('/api/orders', json=self.order_payload()).json()
        reviewer = self.client.post('/api/auth/register', json={
            'full_name': 'Reviewer', 'email': 'reviewer@example.com', 'password': 'strong-password-123',
        }).json()
        with SessionLocal() as db:
            db.get(User, reviewer['user']['id']).is_admin = True
            db.commit()
        headers = self.admin_headers('reviewer@example.com')
        url = f"/api/admin/payments/{created['order_id']}/review"
        unchecked = self.client.post(url, json={
            'decision': 'cancel', 'note': 'No reference submitted',
        }, headers=headers)
        self.assertEqual(unchecked.status_code, 400, unchecked.text)
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 7)
            self.assertEqual(db.get(Order, created['order_id']).status, 'awaiting_payment')
        checked = self.client.post(url, json={
            'decision': 'cancel', 'note': 'No deposit found after checking the receiving account',
            'statement_checked_no_payment': True,
        }, headers=headers)
        self.assertEqual(checked.status_code, 200, checked.text)
        self.assertEqual(checked.json()['status'], 'cancelled')
        with SessionLocal() as db:
            self.assertEqual(db.get(Product, self.product['id']).stock_quantity, 8)


if __name__ == '__main__':
    unittest.main()
