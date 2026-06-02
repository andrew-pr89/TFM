"""
Clasificador semántico de actividades — fallback cuando el LLM no reconoce una actividad.

Este módulo proporciona una clasificación heurística basada en palabras clave
para actividades desconocidas (alimentos, transportes, electrodomésticos, etc),
complementando el análisis del LLM.
"""

import re
import logging

log = logging.getLogger(__name__)


# Diccionario de palabras clave → categoría de actividad
ACTIVITY_KEYWORDS_MAP = {
    # ════════════════════════════════════════════════════════════════════════════════
    # TRANSPORTE
    # ════════════════════════════════════════════════════════════════════════════════
    "coche_gasolina": [
        "coche", "carro", "auto", "automóvil", "gasolina", "gasolina", "nafta",
        "vehículo", "vehículo privado", "coche gasolina", "coche de gasolina",
    ],
    "coche_diesel": [
        "diesel", "gasoil", "diésel", "coche diesel", "vehículo diesel",
    ],
    "coche_electrico": [
        "eléctrico", "coche eléctrico", "coche electrico", "tesla", "bhdi electric",
        "auto eléctrico", "coche verde", "coche eco",
    ],
    "moto": [
        "moto", "motocicleta", "motociclismo", "motobike", "bike", "moto gasolina",
        "ciclomotor", "scooter gasolina",
    ],
    "moto_electrica": [
        "moto eléctrica", "moto electrica", "motocicleta eléctrica", "scooter eléctrico",
        "scooter electrico", "moto eco",
    ],
    "patinete_electrico": [
        "patinete", "patinete eléctrico", "patinete electrico", "scooter eléctrico",
        "monopatin electrico", "e-scooter",
    ],
    "taxi": [
        "taxi", "vtc", "uber", "cabify", "taxista", "taxímetro", "taxi app",
        "coche de alquiler", "servicio taxi",
    ],
    "avion_domestico": [
        "avión", "avion", "vuelo nacional", "vuelo doméstico", "vuelo domestico",
        "vuelo interno", "ruta aérea nacional", "aeroplano doméstico",
    ],
    "avion_internacional": [
        "vuelo internacional", "avión internacional", "avion internacional",
        "vuelo transoceánico", "ruta aérea internacional", "vuelo intercontinental",
    ],
    "crucero": [
        "crucero", "barco crucero", "buque", "transatlántico", "crucero viaje",
    ],
    "tren": [
        "tren", "ferrocarril", "tren de alta velocidad", "ave", "renfe",
        "tren rápido", "tren regional", "ferrocarril nacional",
    ],
    "metro": [
        "metro", "metropolitano", "subterráneo", "underground", "subway",
        "línea de metro", "transporte subterráneo",
    ],
    "autobus": [
        "autobús", "autobus", "bus", "transporte urbano", "línea urbana",
        "línea de autobús", "transporte público urbano", "omnibus",
    ],
    "autobus_interurbano": [
        "autobús interurbano", "autobus interurbano", "bus interurbano",
        "transporte interurbano", "línea interurbana", "bus de larga distancia",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ENERGÍA Y HOGAR
    # ════════════════════════════════════════════════════════════════════════════════
    "electricidad_es": [
        "electricidad", "electrico", "eléctrico", "kwh", "consumo eléctrico",
        "energía eléctrica", "luz", "factura luz", "corriente eléctrica",
    ],
    "gas_natural": [
        "gas", "gas natural", "calefacción gas", "calefacción a gas",
        "gas calefacción", "energía gas", "suministro gas",
    ],
    "calefaccion_gasoil": [
        "gasoil", "gas oil", "calefacción gasoil", "calefacción aceite",
        "combustible calefacción", "aceite combustible", "fuel",
    ],
    "aire_acondicionado": [
        "aire acondicionado", "aire acondicionamiento", "climatización",
        "aire", "sistema aire", "AC", "aire frío", "refrigeración",
    ],
    "lavadora": [
        "lavadora", "lavar", "lavandería", "máquina lavar", "ciclo lavadora",
    ],
    "secadora": [
        "secadora", "secar ropa", "máquina secar", "secado",
    ],
    "lavavajillas": [
        "lavavajillas", "lavaplatos", "máquina lavar platos", "ciclo lavavajillas",
    ],
    "television": [
        "televisión", "television", "tv", "tele", "pantalla", "televisor",
        "ver tv", "consumo tv",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ALIMENTOS - PROTEÍNAS
    # ════════════════════════════════════════════════════════════════════════════════
    "carne_vacuno": [
        "vaca", "res", "vacuno", "beef", "carne roja", "filete", "bistec",
        "chuletón", "chuleta", "lomo", "solomillo", "entrecot", "carne molida",
        "picadillo", "ternera", "vaquero", "bife", "asado", "costilla de res",
        "ternera lechal", "añojo",
    ],
    "carne_cerdo": [
        "cerdo", "puerco", "pork", "jamón", "chuleta de cerdo", "costilla",
        "tocino", "bacon", "lardo", "rabo de cerdo", "panceta", "salchicha",
        "carne cerdo",
    ],
    "carne_pollo": [
        "pollo", "chicken", "pechuga", "muslo", "ala", "alita", "pata",
        "contramuslo", "chuleta de pollo", "poularde", "ave", "pollo entero",
    ],
    "pescado": [
        "pescado", "fish", "salmón", "trucha", "bacalao", "atún", "pez",
        "seabass", "dorada", "merluza", "lenguado", "mero", "lubina",
        "sardina", "anchoa", "boquerones", "pez espada", "caballa",
    ],
    "marisco": [
        "marisco", "camarón", "camarones", "gamba", "langosta", "mejillón",
        "almeja", "ostra", "pulpo", "calamar", "sepia", "erizo", "cangrejo",
        "langostino", "cigala",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ALIMENTOS - LÁCTEOS Y DERIVADOS
    # ════════════════════════════════════════════════════════════════════════════════
    "lacteos_leche": [
        "leche", "milk", "yogurt", "yogur", "batido", "batido lácteo",
        "leche entera", "leche desnatada", "leche semidesnatada",
    ],
    "queso": [
        "queso", "cheese", "queso fresco", "queso curado", "queso de oveja",
        "queso azul", "mozzarella", "manchego", "emmental",
    ],
    "huevos": [
        "huevo", "egg", "tortilla", "revuelto", "frito", "cocido", "pasado por agua",
        "huevos de corral",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ALIMENTOS - VEGETALES Y LEGUMBRES
    # ════════════════════════════════════════════════════════════════════════════════
    "verduras": [
        "verdura", "vegetales", "lechuga", "tomate", "cebolla", "zanahoria",
        "brócoli", "calabacín", "coliflor", "pepino", "pimiento", "berenjena",
        "espinaca", "acelga", "col", "repollo", "ajo", "puerro", "remolacha",
        "nabo", "alcachofa", "espárrago", "champiñón", "seta", "verduras cocidas",
    ],
    "cereales": [
        "pasta", "espagueti", "macarrones", "fideos", "pan", "tostadas",
        "arroz", "grano", "trigo", "avena", "cebada", "centeno", "harina",
        "galleta", "biscocho", "croissant", "magdalena", "cereal", "granola",
    ],
    "legumbres": [
        "lentejas", "lenteja", "garbanzos", "garbanzo", "judía", "judías",
        "alubia", "alubias", "guisantes", "guisante", "haba", "habas",
        "soja", "soya", "frijoles", "frijol", "lupino", "altramuz",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ALIMENTOS - FRUTAS
    # ════════════════════════════════════════════════════════════════════════════════
    "frutas": [  # nota: en seed_data es "fruta" singular
        "fruta", "manzana", "naranja", "plátano", "banana", "fresa", "fresas",
        "uva", "uvas", "pera", "melocotón", "durazno", "piña", "piñas",
        "limón", "lima", "kiwi", "melón", "sandía", "cerezas", "cereza",
        "higo", "dátil", "coco", "mangos", "mango", "papaya", "frutas secas",
        "pasas", "ciruela", "albaricoque", "damasco", "frambuesa", "arándano",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # ALIMENTOS - OTROS
    # ════════════════════════════════════════════════════════════════════════════════
    "comida_rapida": [
        "hamburguesa", "burger", "pizza", "hotdog", "sándwich", "sandwich",
        "empanada", "croqueta", "croquetas", "nugget", "nuggets", "fast food",
        "comida rápida", "kebab", "taco", "burrito",
    ],
    "cafe": [
        "café", "coffee", "cappuccino", "latte", "espresso", "cortado",
        "americano", "café con leche", "café solo", "descafeinado",
    ],
    "chocolate": [
        "chocolate", "chocolate caliente", "bebida chocolate", "cacao",
    ],
    "alcohol_cerveza": [
        "cerveza", "beer", "caña", "clara", "negra", "rubia", "cerveza artesana",
        "cerveza sin alcohol",
    ],
    "alcohol_vino": [
        "vino", "wine", "copa de vino", "vino tinto", "vino blanco",
        "vino rosado", "espumoso", "champagne", "cava",
    ],
    "agua_embotellada": [
        "agua", "water", "agua mineral", "agua embotellada", "agua de manantial",
        "agua con gas", "agua sin gas", "bebida agua",
    ],
    "refresco_lata": [
        "refresco", "soda", "coca", "fanta", "sprite", "bebida azucarada",
        "bebida carbónica", "gaseosa", "cola",
    ],
    "zumo": [
        "zumo", "juice", "jugo", "smoothie", "batido", "jugo natural",
        "zumo de naranja", "zumo de manzana",
    ],
    "aceite_oliva": [
        "aceite", "aceite de oliva", "aceite virgen", "aceite extra virgen",
        "aceite de semilla", "aceite de girasol", "aceite de maíz",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # RESIDUOS
    # ════════════════════════════════════════════════════════════════════════════════
    "residuo_mixto": [
        "basura", "residuo", "desperdicio", "resto", "residuos mixtos",
        "basura doméstica", "residuos no reciclables",
    ],
    "residuo_reciclado": [
        "reciclaje", "reciclado", "papel reciclado", "vidrio reciclado",
        "plástico reciclado", "aluminio reciclado", "residuo reciclable",
    ],

    # ════════════════════════════════════════════════════════════════════════════════
    # COMPRAS Y PRODUCTOS
    # ════════════════════════════════════════════════════════════════════════════════
    "ropa_nueva": [
        "ropa", "ropa nueva", "prenda", "prenda de ropa", "camiseta", "pantalón",
        "falda", "vestido", "abrigo", "chaqueta", "jersey",
    ],
    "zapatillas": [
        "zapatilla", "zapatillas", "zapato", "zapatos", "tenis", "calzado",
        "zapatilla deportiva", "zapatilla de deporte",
    ],
    "libro_nuevo": [
        "libro", "libro nuevo", "novela", "editorial", "publicación",
    ],
    "smartphone": [
        "smartphone", "teléfono", "móvil", "telefono celular", "iphone",
        "teléfono inteligente", "teléfono móvil", "celular",
    ],
    "portatil": [
        "laptop", "portátil", "portatil", "ordenador", "computadora",
        "ordenador portátil", "computadora portátil", "notebook",
    ],
    "streaming": [
        "streaming", "netflix", "spotify", "servicio streaming", "plataforma streaming",
        "música streaming", "vídeo streaming", "reproducción en streaming",
    ],
    "gimnasio": [
        "gimnasio", "gym", "entrenamiento", "fitness", "deporte", "ejercicio",
        "sala de fitness", "centro deportivo", "actividad física",
    ],
}


def classify_activity_by_keywords(activity_name: str, main_category: str | None = None) -> tuple[str | None, float]:
    """
    Intenta clasificar una actividad desconocida usando keywords.

    Args:
        activity_name: Nombre/descripción de la actividad a clasificar
        main_category: Si se conoce (ej: "Transporte"), usar para filtrar resultados

    Returns:
        Tupla (categoría, confianza) donde:
        - categoría: nombre de la categoría (coche_gasolina, etc.) o None
        - confianza: valor entre 0.0 y 1.0 indicando seguridad de la clasificación
    """
    if not activity_name or not activity_name.strip():
        return None, 0.0

    activity_lower = activity_name.lower().strip()
    max_confidence = 0.0
    best_category = None

    for category, keywords in ACTIVITY_KEYWORDS_MAP.items():
        for keyword in keywords:
            # Búsqueda: palabra clave contenida en la actividad o viceversa
            if keyword in activity_lower or activity_lower in keyword:
                # Exactitud: basada en similitud de longitud
                keyword_len = len(keyword)
                activity_len = len(activity_lower)
                
                # Si hay coincidencia exacta → confianza muy alta
                if keyword == activity_lower:
                    confidence = 0.95
                # Si la palabra clave está contenida completamente
                elif keyword in activity_lower:
                    confidence = min(keyword_len / activity_len, 0.9)
                # Si la actividad está dentro del keyword
                elif activity_lower in keyword:
                    confidence = min(activity_len / keyword_len, 0.85)
                else:
                    confidence = 0.5

                if confidence > max_confidence:
                    max_confidence = confidence
                    best_category = category

    return best_category, max_confidence


def should_ask_for_clarification(activity_name: str, confidence_threshold: float = 0.6) -> bool:
    """
    Determina si se debe pedir clarificación sobre una actividad desconocida.

    Args:
        activity_name: Nombre de la actividad
        confidence_threshold: Mínimo de confianza para NO pedir clarificación

    Returns:
        True si se debe pedir clarificación, False si hay suficiente confianza
    """
    _, confidence = classify_activity_by_keywords(activity_name)
    return confidence < confidence_threshold


def get_clarification_question(activity_name: str, activity_type: str = "actividad") -> str:
    """
    Genera una pregunta amable para aclarar el tipo de actividad.

    Args:
        activity_name: Nombre de la actividad
        activity_type: Tipo de actividad ("alimento", "transporte", etc.)

    Returns:
        Pregunta en español pidiendo clasificación
    """
    category, confidence = classify_activity_by_keywords(activity_name)

    if confidence > 0.7:  # Bastante seguro
        return (
            f"¿Es '{activity_name}' realmente {activity_type}? "
            f"¿Puedes ser más específico o dar más detalles?"
        )
    else:
        return (
            f"Desconozco '{activity_name}' como {activity_type}. "
            f"¿Puedes describir qué es con más detalle o dar un ejemplo?"
        )


# Pruebas locales
if __name__ == "__main__":
    test_activities = [
        "chuletón", "filete", "salmón", "arroz", "yogurt",
        "papas", "xyzalimento", "pizza", "café", "uber",
        "metro", "tesla", "tren", "Netflix"
    ]

    for activity in test_activities:
        category, conf = classify_activity_by_keywords(activity)
        print(f"{activity:20} → {category:20} (conf: {conf:.2f})")
