import csv
import random
import os
from datetime import datetime, timedelta

# ==============================
# CONFIGURACIÓN
# ==============================
NUM_FILAS = 1000
PORCENTAJE_ERRORES = 0.02  # 2% errores

# Detectar carpeta Downloads automáticamente
DOWNLOADS_PATH = os.path.join(os.path.expanduser("~"), "Downloads")
OUTPUT_FILE = os.path.join(DOWNLOADS_PATH, "ventas_1000_filas.csv")

# ==============================
# DATA BASE
# ==============================
productos = {
    "Laptop": 1200,
    "Mouse": 25,
    "Teclado": 45,
    "Monitor": 300,
    "Impresora": 180,
    "Tablet": 450,
    "Auriculares": 80,
    "Silla Gamer": 350
}

clientes = [
    "Juan Perez", "Ana Lopez", "Carlos Ruiz", "Laura Diaz",
    "Miguel Torres", "Sofia Martinez", "Pedro Gomez",
    "Lucia Herrera", "Andres Castro", "Valeria Mendez"
]

regiones = ["Centro", "Norte", "Sur", "Este", "Oeste"]

fecha_inicio = datetime(2024, 1, 1)

# ==============================
# FUNCIONES
# ==============================
def generar_fecha():
    dias_random = random.randint(0, 364)
    return (fecha_inicio + timedelta(days=dias_random)).strftime("%Y-%m-%d")

def generar_fila():
    producto = random.choice(list(productos.keys()))
    precio_base = productos[producto]
    
    precio = round(precio_base * random.uniform(0.9, 1.1), 2)
    cantidad = random.randint(1, 5)
    
    fila = {
        "fecha": generar_fecha(),
        "producto": producto,
        "cliente": random.choice(clientes),
        "precio": precio,
        "cantidad": cantidad,
        "region": random.choice(regiones)
    }
    
    # Errores intencionales
    if random.random() < PORCENTAJE_ERRORES:
        tipo_error = random.choice(["fecha", "cliente", "precio"])
        if tipo_error == "fecha":
            fila["fecha"] = ""
        elif tipo_error == "cliente":
            fila["cliente"] = ""
        elif tipo_error == "precio":
            fila["precio"] = "N/A"
    
    return fila

# ==============================
# EXPORTAR
# ==============================
with open(OUTPUT_FILE, mode="w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=["fecha", "producto", "cliente", "precio", "cantidad", "region"]
    )
    writer.writeheader()
    
    for _ in range(NUM_FILAS):
        writer.writerow(generar_fila())

print(f"✅ Archivo generado correctamente en: {OUTPUT_FILE}")