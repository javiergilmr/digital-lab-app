# Columnas canónicas del sistema
REQUIRED_FIELDS = {
    "fecha": ["fecha", "date", "día", "fecha_venta"],
    "producto": ["producto", "item", "descripcion", "descripción"],
    "cantidad": ["cantidad", "qty", "unidades"],
    "precio_unitario": ["precio_unitario", "precio", "unit_price"],
    "total": ["total", "importe", "monto"]
}

SALES_SCHEMA = {
    # Sin estas columnas no hay análisis posible
    "required": {
        "date": ["date", "fecha", "day", "createdat", "fecha_venta", "transaction_date"],
        "product": ["product", "producto", "item", "sku", "descripcion", "product_name", "nombre_producto"],
        "quantity": ["quantity", "qty", "cantidad", "units"],
        "price": ["price", "precio", "unit_price", "precio_unitario", "amount", "monto"]
    },
    # Si vienen, enriquecen la limpieza y el análisis; si no, todo sigue funcionando
    "optional": {
        "product_id": ["product_id", "id_producto", "codigo_producto", "sku_id"],
        "category": ["category", "categoria", "rubro", "linea", "familia"],
        "store_id": ["store_id", "id_tienda", "tienda_id", "sucursal_id", "codigo_tienda"],
        "store_city": ["store_city", "city", "ciudad", "ciudad_tienda", "municipio"],
        "net_sales": ["net_sales", "venta_neta", "ventas_netas", "total_neto", "net_amount"],
        "unit_cost": ["unit_cost", "costo_unitario", "cost", "costo"],
        "total_cost": ["total_cost", "costo_total"],
        "profit": ["profit", "utilidad", "ganancia"]
    },
    "types": {
        "date": "datetime",
        "product": "str",
        "quantity": "int",
        "price": "float",
        "product_id": "str",
        "category": "str",
        "store_id": "str",
        "store_city": "str",
        "net_sales": "float",
        "unit_cost": "float",
        "total_cost": "float",
        "profit": "float"
    },
    "labels": {
        "date": "Fecha",
        "product": "Producto",
        "quantity": "Cantidad",
        "price": "Precio unitario",
        "product_id": "Código de producto",
        "category": "Categoría",
        "store_id": "Tienda",
        "store_city": "Ciudad",
        "net_sales": "Venta neta",
        "unit_cost": "Costo unitario",
        "total_cost": "Costo total",
        "profit": "Utilidad"
    }
}

ALL_FIELDS = {**SALES_SCHEMA["required"], **SALES_SCHEMA["optional"]}

ALIASES = {
    "date": ["date", "createdat", "day","fecha"],
    "product": ["product", "item", "sku", "name","producto"],
    "cliente": ["customer", "client", "buyer"],
    "quantity": ["qty", "quantity", "units", "unitssold","cantidad"],
    "price": ["price", "amount", "cost", "value","precio"],
    "region": ["region", "zone", "area"]
}
