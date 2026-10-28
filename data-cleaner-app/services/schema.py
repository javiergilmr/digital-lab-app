# Columnas canónicas del sistema
REQUIRED_FIELDS = {
    "fecha": ["fecha", "date", "día", "fecha_venta"],
    "producto": ["producto", "item", "descripcion", "descripción"],
    "cantidad": ["cantidad", "qty", "unidades"],
    "precio_unitario": ["precio_unitario", "precio", "unit_price"],
    "total": ["total", "importe", "monto"]
}

SALES_SCHEMA = {
    "required": {
        "date": ["date", "fecha", "day", "createdat", "fecha_venta"],
        "product": ["product", "producto", "item", "sku", "descripcion"],
        "quantity": ["quantity", "qty", "cantidad", "units"],
        "price": ["price", "precio", "amount", "monto"]
    },
    "types": {
        "date": "datetime",
        "product": "str",
        "quantity": "int",
        "price": "float"
    }
}

ALIASES = {
    "date": ["date", "createdat", "day","fecha"],
    "product": ["product", "item", "sku", "name","producto"],
    "cliente": ["customer", "client", "buyer"],
    "quantity": ["qty", "quantity", "units", "unitssold","cantidad"],
    "price": ["price", "amount", "cost", "value","precio"],
    "region": ["region", "zone", "area"]
}


