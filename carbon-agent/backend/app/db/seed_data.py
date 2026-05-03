"""
Factores de emisión iniciales.

Fuentes:
  - DEFRA (UK Government GHG Conversion Factors 2023)
  - IPCC AR6
  - Red Eléctrica de España (REE 2023) para electricidad
  - Poore & Nemecek 2018 (alimentación)
  - WRAP Textiles 2022 (ropa)

Unidades:
  km       → por kilómetro recorrido
  kg       → por kilogramo consumido / transportado
  kWh      → por kilovatio-hora de electricidad
  hora     → por hora de uso
  unidad   → por pieza / evento / ciclo
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
        "display_name": "Moto / ciclomotor (gasolina)",
        "unit": "km",
        "factor_kg_co2e": 0.114,
        "source": "DEFRA 2023 — motorbike, average",
    },
    {
        "category": "moto_electrica",
        "display_name": "Moto eléctrica",
        "unit": "km",
        "factor_kg_co2e": 0.022,
        "source": "DEFRA 2023 — electric motorbike, mix eléctrico europeo",
    },
    {
        "category": "patinete_electrico",
        "display_name": "Patinete eléctrico",
        "unit": "km",
        "factor_kg_co2e": 0.025,
        "source": "CE Delft 2020 — e-scooter lifecycle",
    },
    {
        "category": "taxi",
        "display_name": "Taxi / VTC (Uber)",
        "unit": "km",
        "factor_kg_co2e": 0.211,
        "source": "DEFRA 2023 — taxi, average",
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
        "category": "crucero",
        "display_name": "Crucero (por día)",
        "unit": "unidad",
        "factor_kg_co2e": 163.0,
        "source": "ICCT 2019 — cruise ship per passenger day",
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
    {
        "category": "autobus_interurbano",
        "display_name": "Autobús interurbano",
        "unit": "km",
        "factor_kg_co2e": 0.068,
        "source": "DEFRA 2023 — coach average",
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
    {
        "category": "aire_acondicionado",
        "display_name": "Aire acondicionado",
        "unit": "hora",
        "factor_kg_co2e": 0.362,
        "source": "Estimación: 2 kWh/h × REE 2023 factor España",
    },
    {
        "category": "lavadora",
        "display_name": "Lavadora (ciclo)",
        "unit": "unidad",
        "factor_kg_co2e": 0.272,
        "source": "DEFRA 2023 — washing machine cycle, 1.5 kWh",
    },
    {
        "category": "secadora",
        "display_name": "Secadora (ciclo)",
        "unit": "unidad",
        "factor_kg_co2e": 0.724,
        "source": "DEFRA 2023 — tumble dryer cycle, 4 kWh",
    },
    {
        "category": "lavavajillas",
        "display_name": "Lavavajillas (ciclo)",
        "unit": "unidad",
        "factor_kg_co2e": 0.362,
        "source": "DEFRA 2023 — dishwasher cycle, 2 kWh",
    },
    {
        "category": "television",
        "display_name": "Televisión",
        "unit": "hora",
        "factor_kg_co2e": 0.036,
        "source": "Estimación: 0.2 kWh/h × REE 2023",
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
        "category": "carne_procesada",
        "display_name": "Carne procesada (embutidos, frankfurt)",
        "unit": "kg",
        "factor_kg_co2e": 11.0,
        "source": "Poore & Nemecek 2018 — processed meat average",
    },
    {
        "category": "pescado",
        "display_name": "Pescado (promedio)",
        "unit": "kg",
        "factor_kg_co2e": 6.1,
        "source": "Poore & Nemecek 2018",
    },
    {
        "category": "marisco",
        "display_name": "Marisco / mariscos",
        "unit": "kg",
        "factor_kg_co2e": 11.4,
        "source": "Poore & Nemecek 2018 — crustaceans average",
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
        "category": "huevos",
        "display_name": "Huevos",
        "unit": "unidad",
        "factor_kg_co2e": 0.196,
        "source": "Poore & Nemecek 2018 — eggs per unit (~60g)",
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
    {
        "category": "cafe",
        "display_name": "Café",
        "unit": "kg",
        "factor_kg_co2e": 28.5,
        "source": "Poore & Nemecek 2018 — coffee beans",
    },
    {
        "category": "chocolate",
        "display_name": "Chocolate",
        "unit": "kg",
        "factor_kg_co2e": 46.4,
        "source": "Poore & Nemecek 2018 — dark chocolate",
    },
    {
        "category": "alcohol_cerveza",
        "display_name": "Cerveza",
        "unit": "litro",
        "factor_kg_co2e": 1.04,
        "source": "Poore & Nemecek 2018 — beer",
    },
    {
        "category": "alcohol_vino",
        "display_name": "Vino",
        "unit": "litro",
        "factor_kg_co2e": 1.79,
        "source": "Poore & Nemecek 2018 — wine",
    },
    {
        "category": "comida_rapida",
        "display_name": "Comida rápida (hamburguesa/pizza)",
        "unit": "unidad",
        "factor_kg_co2e": 2.5,
        "source": "Estimación basada en Poore & Nemecek 2018 — mixed ingredients",
    },
    {
        "category": "aceite_oliva",
        "display_name": "Aceite de oliva",
        "unit": "litro",
        "factor_kg_co2e": 6.0,
        "source": "Poore & Nemecek 2018 — olive oil",
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
        "category": "zapatillas",
        "display_name": "Zapatillas / calzado",
        "unit": "unidad",
        "factor_kg_co2e": 14.0,
        "source": "MIT Scope 3 — footwear average",
    },
    {
        "category": "libro_nuevo",
        "display_name": "Libro nuevo",
        "unit": "unidad",
        "factor_kg_co2e": 2.71,
        "source": "Book Industry Study Group 2008 — average book",
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

    # ── OCIO / SERVICIOS ─────────────────────────────────────────────────────
    {
        "category": "streaming",
        "display_name": "Streaming (Netflix/Spotify, por mes)",
        "unit": "unidad",
        "factor_kg_co2e": 0.036,
        "source": "Carbon Trust 2021 — video streaming per hour × 10h/mes",
    },
    {
        "category": "gimnasio",
        "display_name": "Sesión de gimnasio",
        "unit": "unidad",
        "factor_kg_co2e": 0.502,
        "source": "Estimación: desplazamiento medio 3km coche + instalación",
    },
    {
        "category": "hotel",
        "display_name": "Hotel (por noche)",
        "unit": "unidad",
        "factor_kg_co2e": 22.6,
        "source": "Cornell Hotel Sustainability Benchmarking 2022",
    },
]