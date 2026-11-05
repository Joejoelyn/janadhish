from __future__ import annotations

import http.client
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / 'frontend'
BACKEND_HOST = '127.0.0.1'
BACKEND_PORT = 8000

PAGE_ROUTES = {
    '/': '/index.html',
    '/shop': '/shop.html',
    '/custom-made': '/custom-made.html',
    '/cart': '/cart.html',
    '/checkout': '/checkout.html',
    '/login': '/login.html',
    '/register': '/register.html',
    '/account': '/account.html',
    '/about': '/about.html',
    '/contact': '/contact.html',
    '/faq': '/faq.html',
    '/privacy-policy': '/privacy.html',
    '/terms': '/terms.html',
    '/shipping-policy': '/shipping.html',
    '/favicon.ico': '/assets/images/logo/brand-mark.svg',
}
API_ROUTES = ('/api/', '/docs', '/redoc', '/openapi.json')
HOP_BY_HOP_HEADERS = {
    'connection',
    'content-length',
    'host',
    'keep-alive',
    'proxy-authenticate',
    'proxy-authorization',
    'te',
    'trailer',
    'transfer-encoding',
    'upgrade',
}


class FrontendRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONTEND_DIR), **kwargs)

    def translate_path(self, path: str) -> str:
        route = urlsplit(path).path
        mapped_page = PAGE_ROUTES.get(route)
        if mapped_page:
            path = mapped_page
        elif re.fullmatch(r'/product/\d+', route):
            path = '/product.html'
        return super().translate_path(path)

    def _is_api_route(self) -> bool:
        path = urlsplit(self.path).path
        return any(path == route or path.startswith(route) for route in API_ROUTES)

    def _proxy_api_request(self) -> None:
        request_body = None
        content_length = self.headers.get('Content-Length')
        if content_length:
            request_body = self.rfile.read(int(content_length))

        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP_HEADERS
        }
        connection = http.client.HTTPConnection(BACKEND_HOST, BACKEND_PORT, timeout=30)
        try:
            connection.request(self.command, self.path, body=request_body, headers=headers)
            response = connection.getresponse()
            body = response.read()
            self.send_response(response.status, response.reason)
            for key, value in response.getheaders():
                if key.lower() not in HOP_BY_HOP_HEADERS:
                    self.send_header(key, value)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
        except OSError as error:
            self.log_error('Backend proxy request failed: %s', error)
            self.send_error(502, 'Backend is unavailable. Start the FastAPI server on port 8000.')
        finally:
            connection.close()

    def do_GET(self) -> None:
        if self._is_api_route():
            self._proxy_api_request()
        else:
            super().do_GET()

    def do_HEAD(self) -> None:
        if self._is_api_route():
            self._proxy_api_request()
        else:
            super().do_HEAD()

    def do_POST(self) -> None:
        self._proxy_api_request()

    def do_PUT(self) -> None:
        self._proxy_api_request()

    def do_PATCH(self) -> None:
        self._proxy_api_request()

    def do_DELETE(self) -> None:
        self._proxy_api_request()

    def do_OPTIONS(self) -> None:
        self._proxy_api_request()


def main() -> None:
    server = ThreadingHTTPServer(('127.0.0.1', 5500), FrontendRequestHandler)
    print('Frontend running at http://127.0.0.1:5500')
    print('API requests are proxied to the FastAPI backend at http://127.0.0.1:8000')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nFrontend server stopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
