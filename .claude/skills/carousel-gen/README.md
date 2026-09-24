# Carruseles Automaticos

Skill de [Claude Code](https://docs.anthropic.com/en/docs/claude-code) para transformar un
**post/copy viral de referencia** en un carrusel de Instagram, eligiendo uno de **7 formatos
narrativos** probados, usando [Kie AI (Nano Banana Pro)](https://kie.ai/).

El estilo visual NUNCA se elige manualmente: se detecta automaticamente ("ADN visual") a
partir de la imagen de referencia que adjuntas en cada ejecucion.

![Formato](https://img.shields.io/badge/Formato-1080x1350px%20(4:5)-green)
![API](https://img.shields.io/badge/API-Kie%20AI%20Nano%20Banana-purple)

---

## Que hace

1. Te pide la **imagen del post viral** que quieres transformar (obligatoria, distinta cada vez)
2. **Analiza su ADN visual**: paleta, tipografia, composicion, jerarquia, tratamiento de
   personajes/objetos, textura, iluminacion, margenes, recursos graficos
3. Te muestra los **7 formatos de carrusel** disponibles y eliges uno
4. Te **recomienda una cantidad de slides** segun el formato y el contenido, y confirmas o ajustas
5. **Transforma el contenido** del post original al formato elegido, preservando su mensaje y tematica
6. Te muestra un **brief detallado slide por slide** para tu aprobacion
7. Solo tras tu aprobacion, **genera todas las imagenes EN PARALELO** via Kie AI

## Los 4 conceptos (no se mezclan)

| Concepto | Que es | Como se define |
|---|---|---|
| **Imagen de referencia** | El post/copy viral que adjuntas | Obligatoria, distinta en cada ejecucion |
| **Tipo de carrusel** | Uno de los 7 formatos narrativos | Lo eliges tu, una vez por ejecucion |
| **Estilo visual** | Paleta, tipografia, composicion, etc. | Se detecta automaticamente de la referencia — nunca se elige manualmente |
| **Tematica** | El mensaje/tema del contenido | Se infiere de la referencia — se preserva si es emocional, relaciones, familia, sanacion o mirada sistemica |

---

## Requisitos

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) instalado
- Python 3.8+
- API Key de [Kie AI](https://kie.ai/)
- Paquetes Python: `requests`, `python-dotenv`, `Pillow`

## Instalacion

### 1. Clonar el repositorio

```bash
git clone https://github.com/santmun/carruselesdef.git
cd carruselesdef
```

### 2. Instalar dependencias Python

```bash
pip install requests python-dotenv Pillow
```

### 3. Configurar API Key

```bash
cp .env.example .env
```

Edita `.env` y reemplaza `tu-api-key-aqui` con tu API key de [kie.ai](https://kie.ai/).

---

## Uso

### Dentro de Claude Code

```
/carousel-gen
```

No requiere parametros — el flujo pide todo lo necesario paso a paso.

### Los 7 formatos de carrusel

| # | Formato | Idea central |
|---|---|---|
| 1 | **La Gran Noticia** | Estilo titular de prensa/noticiero + interpretacion personal |
| 2 | **Collage Visual** | Estilo diario/scrapbook, fragmentos íntimos |
| 3 | **Meme Cartoon** | Viñetas tipo comic con humor situacional |
| 4 | **Recopilacion de Ideas (Listicle)** | Titulo con numero + items enumerados |
| 5 | **Versus / Pantalla Dividida** | Comparacion clara entre dos posturas |
| 6 | **Carrusel Interactivo** | Invita a autoevaluarse / participar |
| 7 | **Tipos de X** | Presenta distintos "tipos" de algo, con identificacion |

### Workflow paso a paso

```
PASO 1: Adjuntar imagen de referencia (OBLIGATORIO, bloqueante)
   No se puede continuar sin ella

PASO 2: Analisis automatico del ADN visual
   Paleta, tipografia, composicion, jerarquia, personajes/objetos,
   textura, iluminacion, margenes, recursos graficos

PASO 3: Elegir uno de los 7 formatos de carrusel

PASO 4: Confirmar cantidad de slides
   Se recomienda un numero segun formato + contenido, nunca es fijo

PASO 5: Transformacion del contenido al formato elegido
   Preservando mensaje, emocion y tematica del post original

PASO 6: Brief detallado slide por slide para aprobacion

PASO 7: Generacion en paralelo (solo tras aprobacion)
```

### Standalone (sin Claude Code)

El script `generate-carousel.py` requiere un `brief.json` ya creado en el bundle (lo crea
el workflow de `SKILL.md`, no lo genera el script):

```bash
# Generacion completa (requiere brief.json en outputs/bundles/<bundle_id>/)
python3 scripts/generate-carousel.py "mi-bundle-id"

# Solo ver el brief (sin generar)
python3 scripts/generate-carousel.py "mi-bundle-id" --dry-run

# Regenerar slides especificos
python3 scripts/generate-carousel.py "mi-bundle-id" --regenerate-slides "2,4"

# Saltar preguntas interactivas de logos (para automatizacion)
python3 scripts/generate-carousel.py "mi-bundle-id" --skip-interactive
```

---

## Estructura de archivos

```
carruselesdef/
├── README.md
├── .env.example                     # Template de configuracion
├── .gitignore
├── .claude/
│   └── skills/
│       └── carousel-gen/
│           └── SKILL.md             # Definicion del skill para Claude Code
└── scripts/
    └── generate-carousel.py         # Script principal de generacion
```

### Estructura del bundle (output)

```
outputs/bundles/[bundle_id]/
└── brief.json                       # Fuente de verdad: referencia, ADN visual, formato, slides
    carousel/
    ├── carousel-01.png              # Imagenes generadas
    ├── carousel-02.png
    ├── ...
    ├── manifest.json                # Metadata de generacion (formato, cantidad, referencia usada)
    ├── carousel-assets-needed.md    # Guia de logos opcionales
    └── assets/
        ├── viral-reference.png      # Imagen de referencia viral (OBLIGATORIA)
        └── {entidad}.png            # Logos opcionales de herramientas detectadas
```

---

## `brief.json`: la fuente de verdad

Cada bundle tiene un `brief.json` que concentra todo lo necesario para generar (y para
regenerar fielmente) el carrusel:

```json
{
  "bundle_id": "...",
  "reference_image": {
    "local_path": "carousel/assets/viral-reference.png",
    "analysis": {
      "tema_mensaje": "...",
      "copy_estructura": "...",
      "emocion_predominante": "...",
      "elementos_impacto": "..."
    }
  },
  "visual_dna": {
    "paleta_colores": { "dominantes": ["..."], "acentos": ["..."], "fondo": "..." },
    "tipografia": { "tratamiento": "...", "peso": "...", "estilo": "..." },
    "tipo_imagen": "foto real | ilustracion | texto plano | mixto",
    "composicion_base": "...",
    "jerarquia_visual": "...",
    "tratamiento_personajes_objetos": "...",
    "textura": "...",
    "iluminacion": "...",
    "margenes": "...",
    "recursos_graficos": ["...", "..."]
  },
  "carousel_type": "la-gran-noticia | collage-visual | meme-cartoon | recopilacion-ideas | versus | interactivo | tipos-de-x",
  "slide_count": { "recommended": "...", "confirmed": "..." },
  "slides": [
    {
      "number": 1,
      "role": "...",
      "narrative_objective": "...",
      "message": "...",
      "exact_text": "...",
      "scene_description": "...",
      "composition": "...",
      "visual_hierarchy": "...",
      "text_placement": "...",
      "key_visual_elements": ["..."],
      "visual_dna_connection": "...",
      "connects_prev": null,
      "connects_next": "...",
      "uses_reference_image_directly": true
    }
  ]
}
```

**Nota importante:** `slide_count.recommended` y `slide_count.confirmed` nunca tienen un
valor fijo — se calculan de nuevo en cada ejecucion segun el formato elegido y la densidad
del contenido de esa referencia especifica.

`uses_reference_image_directly` es `true` UNICAMENTE en el slide 1 — es el unico que recibe
la imagen de referencia real como inspiracion directa. Los demas slides heredan el `visual_dna`
en texto, no la imagen bruta, para poder evolucionar su composicion segun el formato sin dejar
de ser coherentes visualmente.

---

## Como funciona la referencia visual

1. **Slide 1**: se envia la imagen de referencia real a Kie AI como `image_input`, con
   instruccion explicita de crear una pieza NUEVA inspirada en su composicion, jerarquia
   visual, paleta, tipo de imagen, distribucion y sensacion de impacto — sin copiarla
   literalmente.
2. **Slides 2-N**: no reciben la imagen bruta. Reciben el `visual_dna` estructurado como
   texto, para mantener coherencia real (misma paleta, tipografia, tipo de ilustracion,
   textura, iluminacion) mientras la composicion se adapta al rol de cada slide dentro del
   formato elegido.

No existe ninguna biblioteca de estilos ni preset guardado entre ejecuciones — la identidad
visual completa de cada carrusel nace de la imagen de referencia que adjuntas esa vez.

---

## Logos de herramientas (opcional)

Si el contenido menciona herramientas conocidas (Claude, ChatGPT, n8n, etc.), el script las
detecta y, si tienes logos oficiales, puedes colocarlos en `carousel/assets/{entidad}.png`
para integrarlos via `nano-banana-edit`. Este mecanismo es independiente del ADN visual —
no reemplaza ni afecta el estilo detectado de la referencia.

Herramientas detectadas automaticamente:
`n8n` `ChatGPT` `Claude` `Make` `WhatsApp` `Zapier` `Anthropic` `OpenAI` `Gemini`

---

## Costos y tiempos

| Concepto | Valor |
|----------|-------|
| Por imagen | ~$0.10 USD |
| Generacion | **EN PARALELO** (todas al mismo tiempo) |

---

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| El script se queda colgado | Usa `--skip-interactive` y `PYTHONUNBUFFERED=1` |
| No encuentra brief.json | Debe crearse desde el workflow de SKILL.md (Paso 6) antes de ejecutar el script |
| API key no configurada | Crea `.env` con `KIE_AI_API_KEY=tu-key` (copia `.env.example`) |
| No se encuentra la imagen de referencia | Verifica que existe `carousel/assets/viral-reference.png` y que `brief.json` apunta a esa ruta |
| Logos no se integran | Verifica que el archivo `{entidad}.png` existe en `carousel/assets/` |
| Timeout esperando resultado | API sobrecargada, usa `--regenerate-slides` para reintentar |
| Credits insufficient | Recarga creditos en kie.ai, luego usa `--regenerate-slides "6,7,8"` para los que faltaron |
| ModuleNotFoundError | Ejecuta `pip install requests python-dotenv Pillow` |

---

## Personalizacion

### Cambiar aspect ratio

En `scripts/generate-carousel.py`:

```python
ASPECT_RATIO = "4:5"   # Instagram carousel (1080x1350px)
# Cambiar a:
ASPECT_RATIO = "1:1"   # Cuadrado (1080x1080px)
ASPECT_RATIO = "9:16"  # Stories (1080x1920px)
```

### Agregar nuevas herramientas detectadas (para logos opcionales)

Busca el diccionario `KNOWN_ENTITIES` en `generate-carousel.py` y agrega las tuyas.

---

## Licencia

MIT

---

## Creditos

- Imagenes generadas con [Kie AI - Nano Banana Pro](https://kie.ai/)
- Skill diseñado para [Claude Code](https://docs.anthropic.com/en/docs/claude-code) de Anthropic
