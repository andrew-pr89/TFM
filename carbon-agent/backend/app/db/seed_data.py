"""
Factores de emisión iniciales.

Fuentes:
  - DEFRA (UK Government GHG Conversion Factors 2023)
  - IPCC AR6
  - Red Eléctrica de España (REE 2023) para electricidad

Unidades:
  km       → por kilómetro recorrido
  kg       → por kilogramo consumido / transportado
  kWh      → por kilovatio-hora de electricidad
  hora     → por hora de uso
  unidad   → por pieza / evento
  litro    → por litro consumido
"""

EMISSION_FACTORS = [
    # ── TRANSPORTE ──────────────────────────────────────────────────────────
    {
        "category": "coche_gasolina",
        "display_name": "Coche (gasolina)",
        "unit": "km",
        "factor_kg_co2e": 0.192,
        "source": "DEFRA 2023 — passenger car, petrol, average",
    },
    {
        "category": "coche_diesel",
        "display_name": "Coche (diésel)",
        "unit": "km",
        "factor_kg_co2e": 0.171,
        "source": "DEFRA 2023 — passenger car, diesel, average",
    },
    {
        "category": "coche_electrico",
        "display_name": "Coche eléctrico",
        "unit": "km",
        "factor_kg_co2e": 0.053,
        "source": "DEFRA 2023 — BEV, mix eléctrico europeo",
    },
    {
        "category": "moto",
        "display_name": "Moto / ciclomotor",
        "unit": "km",
        "factor_kg_co2e": 0.114,
        "source": "DEFRA 2023 — motorbike, average",
    },
    {
        "category": "avion_domestico",
        "display_name": "Avión (vuelo doméstico)",
        "unit": "km",
        "factor_kg_co2e": 0.255,
        "source": "DEFRA 2023 — domestic flight, economy class",
    },
    {
        "category": "avion_internacional",
        "display_name": "Avión (vuelo internacional)",
        "unit": "km",
        "factor_kg_co2e": 0.195,
        "source": "DEFRA 2023 — long-haul flight, economy class",
    },
    {
        "category": "tren",
        "display_name": "Tren (nacional)",
        "unit": "km",
        "factor_kg_co2e": 0.041,
        "source": "DEFRA 2023 — national rail average",
    },
    {
        "category": "metro",
        "display_name": "Metro / tranvía",
        "unit": "km",
        "factor_kg_co2e": 0.028,
        "source": "DEFRA 2023 — light rail / tram",
    },
    {
        "category": "autobus",
        "display_name": "Autobús urbano",
        "unit": "km",
        "factor_kg_co2e": 0.089,
        "source": "DEFRA 2023 — local bus average",
    },
    # ── ENERGÍA EN HOGAR ────────────────────────────────────────────────────
    {
        "category": "electricidad_es",
        "display_name": "Electricidad (España)",
        "unit": "kWh",
        "factor_kg_co2e": 0.181,
        "source": "REE 2023 — factor de emisión mix eléctrico España",
    },
    {
        "category": "gas_natural",
        "display_name": "Gas natural (hogar)",
        "unit": "kWh",
        "factor_kg_co2e": 0.203,
        "source": "DEFRA 2023 — natural gas, combustion",
    },
    {
        "category": "calefaccion_gasoil",
        "display_name": "Calefacción gasoil",
        "unit": "litro",
        "factor_kg_co2e": 2.68,
        "source": "DEFRA 2023 — burning oil",
    },
    # ── ALIMENTACIÓN ────────────────────────────────────────────────────────
    {
        "category": "carne_vacuno",
        "display_name": "Carne de vacuno",
        "unit": "kg",
        "factor_kg_co2e": 27.0,
        "source": "IPCC AR6 / Poore & Nemecek 2018",
    },
    {
        "category": "carne_cerdo",
        "display_name": "Carne de cerdo",
        "unit": "kg",
        "factor_kg_co2e": 12.1,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "carne_pollo",
        "display_name": "Carne de pollo",
        "unit": "kg",
        "factor_kg_co2e": 6.9,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "pescado",
        "display_name": "Pescado (promedio)",
        "unit": "kg",
        "factor_kg_co2e": 6.1,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "lacteos_leche",
        "display_name": "Leche / lácteos",
        "unit": "litro",
        "factor_kg_co2e": 3.2,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "queso",
        "display_name": "Queso",
        "unit": "kg",
        "factor_kg_co2e": 13.5,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "verduras",
        "display_name": "Verduras y hortalizas",
        "unit": "kg",
        "factor_kg_co2e": 2.0,
        "source": "Poore & Nemecek 2018 — vegetables average",
    },
    {
        "category": "cereales",
        "display_name": "Cereales / pan",
        "unit": "kg",
        "factor_kg_co2e": 1.4,
        "source": "Poore & Nemecek 2018",
    },
    # ── RESIDUOS ────────────────────────────────────────────────────────────
    {
        "category": "residuo_mixto",
        "display_name": "Residuo mezclado (vertedero)",
        "unit": "kg",
        "factor_kg_co2e": 0.587,
        "source": "DEFRA 2023 — landfill waste",
    },
    {
        "category": "residuo_reciclado",
        "display_name": "Residuo reciclado",
        "unit": "kg",
        "factor_kg_co2e": 0.021,
        "source": "DEFRA 2023 — recycled waste",
    },
    # ── COMPRAS ─────────────────────────────────────────────────────────────
    {
        "category": "ropa_nueva",
        "display_name": "Ropa nueva (prenda)",
        "unit": "unidad",
        "factor_kg_co2e": 8.0,
        "source": "WRAP Textiles 2022 — average garment",
    },
    {
        "category": "smartphone",
        "display_name": "Smartphone nuevo",
        "unit": "unidad",
        "factor_kg_co2e": 70.0,
        "source": "Apple / Samsung LCA reports 2023",
    },
    {
        "category": "portatil",
        "display_name": "Portátil nuevo",
        "unit": "unidad",
        "factor_kg_co2e": 400.0,
        "source": "Dell / Apple LCA reports 2023",
    },
]
