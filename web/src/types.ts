export type Product = {
  id: number; sku: string; name: string;
  short_description: string | null; description: string | null;
  fabric_details: string | null; care_instructions: string | null;
  price: number; sale_price: number | null;
  without_pads_price: number | null; with_pads_price: number | null;
  sizes: string[]; colors: string[];
  category: { id: number; name: string; slug: string } | null;
  stock_quantity: number; image_url: string | null; gallery: string[];
  is_new_arrival: boolean; is_best_seller: boolean; is_featured: boolean; is_active: boolean;
};
export type Measurements = { unit: 'inches' | 'cm'; values: Record<string, number> };
export type CartItem = {
  product_id: number; quantity: number; size: string | null; color: string | null;
  with_pads: boolean; measurements?: Measurements;
};
export type User = { id: number; full_name: string; email: string; phone: string | null; is_admin: boolean };
export type Order = {
  id: number; status: string; total: number; created_at: string; payment_token: string | null;
  refunded_amount_paise: number;
  fulfillment: { status: string; carrier: string | null; tracking_reference: string | null } | null;
  items: { product_name: string; quantity: number; unit_price: number; size: string | null; color: string | null; customization_details: { with_pads?: boolean; measurements?: Measurements } | null }[];
};
export type Option = { id: number; name: string; description: string | null; image_url: string | null; additional_price?: number };
