> **WIP GP-180**: format .prst, protokol USB, model dan preset masih data GP-200. Lihat GP180_PORTING_NOTES.md.

# GP-180 Studio — Guía de uso (V0.91)

## ¿Qué es?

GP-180 Studio genera presets (archivos `.prst`) para tu **Valeton GP-180**
a partir de una simple descripción de texto. Escribes lo que quieres escuchar,
una IA crea el preset y solo tienes que enviarlo directamente al GP-180
por USB.

Ejemplos de descripciones:
- *"Sonido clean cristalino con chorus y reverb de resorte"*
- *"Crunch blues cálido estilo Stevie Ray Vaughan"*
- *"Metal moderno, gain saturado, gate ajustado, delay slapback"*
- *"Sonido lead Pink Floyd con delay largo y reverb amplio"*


## Requisitos

- **Python 3.10+** instalado (marcar *"Add python.exe to PATH"* durante la instalación)
- **Tkinter** incluido (es el caso por defecto en Windows si marcas
  *"tcl/tk and IDLE"* durante la instalación de Python)
- **Una clave API** para al menos uno de los proveedores de IA compatibles (ver abajo)
- **Solo para el módulo Batch LUFS**: `pip install sounddevice pyloudnorm`
  (no es necesario para la generación de presets)

La generación de presets solo utiliza la biblioteca estándar de Python.


## Instalación

1. Extraer el contenido del zip en una carpeta de tu elección
2. Copiar `config.example.json` como `config.json`
3. Abrir `config.json` con un editor de texto y pegar tu clave API
4. Hacer doble clic en `GP180_Studio.bat` (o ejecutar `python gp180_studio.py`)

En el primer arranque, la aplicación te pedirá que elijas el slot de inyección
del GP-180 y configures tus claves API a través de una interfaz gráfica.


## Obtener una clave API

La aplicación necesita una clave API para comunicarse con un servicio de IA.
**Esta clave es personal y las llamadas generalmente corren por tu cuenta.**
Estas son las opciones:

### Google Gemini — recomendado para empezar
- **Costo**: gratuito (cuota limitada pero suficiente para uso normal)
- **Tarjeta de crédito**: no requerida
- **Enlace**: https://aistudio.google.com/app/apikey
- **Procedimiento**: inicia sesión con tu cuenta de Google, haz clic en
  *"Create API Key"*, copia la clave generada

### Anthropic Claude
- **Costo**: pago por uso (~$0.003 a $0.015 por preset según el modelo)
- **Tarjeta de crédito**: requerida (créditos prepago, mínimo ~$5)
- **Enlace**: https://console.anthropic.com/settings/keys

### OpenAI (ChatGPT)
- **Costo**: pago por uso (~$0.002 a $0.01 por preset según el modelo)
- **Tarjeta de crédito**: requerida (créditos prepago)
- **Enlace**: https://platform.openai.com/api-keys

### OpenRouter
- **Costo**: pago por uso, acceso a decenas de modelos
- **Autenticación**: mediante OAuth (no hay clave que introducir manualmente —
  un botón *Iniciar sesión* abre el navegador y recupera la clave automáticamente)
- **Enlace**: https://openrouter.ai

### Perplexity
- **Costo**: pago por uso (búsqueda web incluida en el precio)
- **Tarjeta de crédito**: requerida
- **Enlace**: https://www.perplexity.ai/settings/api

**Seguridad**: tu clave API se almacena localmente en tu `config.json`,
cifrada en Windows mediante DPAPI. Nunca se envía a ningún lugar que no sea
el proveedor de IA que hayas elegido.


## La interfaz

```
+------------------------------------------------------------------------+
| GP-180 STUDIO   Nuevo / Afinar   Idioma  ⚙ Config  ★ Funciones         |
+--------------------+---------------------------------------------------+
|  OPCIONES          |  DESCRIBE EL SONIDO QUE QUIERES                   |
|   proveedor        |  [ zona de texto ]                                |
|   modelo           |  EJEMPLOS                                         |
|   micrófono        |  ESTRUCTURA DE LA CANCIÓN                         |
|   búsqueda web     |                                                   |
|                    |  CADENA DE SEÑAL   <nombre del preset mostrado>   |
|  PRESETS GENERADOS |  [PRE][WAH][DST][AMP][NR][CAB][EQ][MOD][DLY]...  |
|   > variante A     |  +-----------------------------------------+     |
|     variante B     |  | AMP  J-120 CL               módulo 4/11 |     |
|     variante C     |  | GAIN 25   BASS 40   MIDDLE 50   ...      |     |
|     ...            |  +-----------------------------------------+     |
|                    |                                                   |
|                    |  Resultado | Registro                             |
|                    |  [ informe detallado ]                            |
+--------------------+---------------------------------------------------+
| ● estado   📍 01-A   🔌 Inyectar       Setlist | ⚡ Generar presets     |
+------------------------------------------------------------------------+
```

La interfaz se adapta a la resolución de tu pantalla. La ventana se abre al
90% de la pantalla, centrada. Solo tiene modo oscuro.

### La cadena de señal

Los 11 módulos del preset se muestran **en una sola línea**, en el orden real
de la cadena, conectados por un cable como en un pedalboard. El color indica
el rol del módulo:

| Color | Módulos | Rol |
|---|---|---|
| **Azul** | `PRE`, `DST`, `AMP` | lo que construye el sonido |
| **Verde** | `NR`, `CAB`, `EQ` | lo que lo moldea |
| **Morado** | `WAH`, `MOD`, `DLY`, `RVB`, `VOL` | lo que lo colorea |

Un módulo con línea punteada está **bypasseado**: en el GP-180 un slot nunca
está vacío, simplemente está desactivado.

Durante una generación, **el cable se ilumina módulo a módulo** y un punto
luminoso lo recorre — ese es el indicador de progreso.

### El inspector de módulos

**Haz clic en un módulo** de la cadena: todos sus ajustes aparecen justo
debajo, con un indicador para los valores entre 0 y 100.

Las tarjetas de la cadena solo muestran un parámetro (con un `+5` que indica
cuántos más esperan). **Las tarjetas muestran el recorrido de la señal, el
inspector muestra los valores.** Esta visualización es de solo lectura.

### El editor live de slot

Al hacer clic en un módulo **de un preset cargado o generado**, se abre una
ventana **Live Control** si el GP-180 está conectado por USB. Puedes cambiar
el modelo de efecto y ajustar sus parámetros en tiempo real, directamente en
el hardware, sin volver a enviar todo el preset. Los cambios se reflejan en
el archivo `.prst` y son visibles en el inspector.

### El LED del GP-180

En la parte inferior izquierda, el indicador **● GP-180** muestra el estado
de la conexión USB:
- **Verde**: USB SysEx + Audio detectados (inyección + LUFS disponibles)
- **Naranja**: USB SysEx solamente (inyección OK, sin audio USB)
- **Gris**: GP-180 no detectado

### Navegar por los presets generados

Una generación escribe 3 variantes por sección, hasta 9 archivos de una vez.
La columna izquierda los lista todos bajo **PRESETS GENERADOS**.

Hacer clic en un preset recompone la cadena y, si el GP-180 está conectado,
lo inyecta automáticamente en el slot configurado (📍). El nombre del preset
aparece junto al título *Cadena de señal*.


## Uso

### Generar presets (modo "Nuevo")

1. Elige tu **proveedor de IA** y tu **modelo** en los menús desplegables
2. Selecciona el **tipo de micrófono** (humbucker, single coil, P90, activo)
   para que la IA adapte el gain y el EQ a tu guitarra
3. Escribe tu descripción en la zona de texto (o elige un ejemplo)
4. Activa o desactiva la **búsqueda web** (ayuda a la IA a identificar el equipo
   real de un artista, pero consume más tokens)
5. Elige la **estructura**:
   - **Detección automática**: la IA decide cuántos presets crear y cómo
     organizarlos (3, 6 o 9 presets)
   - **Forzar roles**: marca los roles que quieres
     (`clean`, `crunch`, `disto`, `lead`) — 3 presets por rol
6. Haz clic en **Generar**
7. Los archivos `.prst` se escriben en la carpeta de salida
   (por defecto `Documents\GP180_Presets`) y aparecen en la lista de la izquierda.
   Si el GP-180 está conectado, el primer preset se inyecta automáticamente
   en el slot configurado.

### Afinar un preset (modo "Afinar")

1. Pasa al modo **Afinar** mediante el selector de la parte superior
2. Carga un archivo `.prst` existente: su cadena se muestra inmediatamente,
   antes de cualquier llamada a la IA
3. Describe los cambios deseados en texto libre
   (*"más gain"*, *"quita el delay"*, *"cambia el amplificador por un Fender"*)
4. Haz clic en **Afinar**
5. La aplicación muestra los **cambios reales** calculados sobre el archivo
   (no lo que el modelo dice haber hecho), la cadena actualizada y los posibles
   avisos (ej: amplificador sin parámetro de Volume)

El preset original nunca se modifica: se escribe una nueva versión en una
subcarpeta con marca de tiempo.

### Optimizar para el directo

En modo Afinar, el botón **Live Ready** adapta un preset creado en casa para
tocar a alto volumen: reducción del gain y de los mixes de reverb/delay,
corte de agudos en el cabinet para eliminar el fizz, ligero boost de medios.
La intención artística y el EQ creativo se preservan. No es necesaria ninguna
descripción — el prompt está preconfigurado.

### Inyectar un preset en el GP-180 (USB)

El botón **🔌 Inyectar** en la parte inferior derecha envía el preset
seleccionado directamente al GP-180 mediante USB SysEx.

- El **slot destino** se muestra permanentemente (📍 01-A por defecto) y se
  puede configurar haciendo clic en el botón del slot
- Una **barra de progreso** chunk a chunk confirma el envío (7 paquetes)
- La inyección también es **automática** en cada selección de la lista,
  si la opción está activada en el diálogo del slot
- El **GP-180 debe estar conectado por USB** y reconocido (LED verde o naranja)

### Armonizar volúmenes (Batch LUFS)

Accesible mediante el menú **★ Funciones → 🎛 Batch Vol.**

El módulo Batch LUFS mide el volumen real de cada preset (norma EBU R128) y
los calibra automáticamente a un objetivo común, sin intervención manual.

**Funcionamiento**:
1. Cargar los `.prst` en el orden de importación en el GP-180
2. Configurar la entrada de audio (interfaz USB del GP-180) y el slot de prueba
3. Hacer clic en **Lanzar**
4. Para cada preset: tocar un acorde en bucle — la app mide el LUFS y ajusta
   los parámetros por USB en tiempo real
5. Validación automática tras 3 segundos de estabilidad dentro de la tolerancia (±0.4 dB)

**Cascada de ajuste** (de más transparente a menos transparente):
- **Volumen del amplificador** (si el modelo lo tiene) — rango 25–100
- **Volumen del CAB** — rango 20–100
- **Patch Volume global** — rango 35–100
- **Gain del amplificador** como último recurso (+10 pts máximo sobre el valor
  inicial, solo si el amplificador no tiene un volumen separado)

Dos tipos de preset: **NORMAL** (objetivo -16 dB LUFS) y **LEAD** (objetivo -11 dB
LUFS). Los archivos corregidos se guardan en una subcarpeta `out/`.

**Requisito**: `pip install sounddevice pyloudnorm`

> ⚠️ **Driver USB Audio obligatorio para el Batch LUFS**: para que la aplicación
> pueda medir la señal de audio del GP-180, el driver USB Audio de Valeton debe
> estar instalado en tu PC. Sin él, la interfaz *Línea (Valeton GP-180)* no
> aparece en la lista de entradas de audio y la medición LUFS es imposible.
>
> El driver probado en Windows 11 está disponible aquí:
> https://www.valeton.net/wpfd_file/valeton-usb-asio-driver-v5-57-2-setup-zip/
>
> **Aviso**: este enlace se proporciona a título orientativo. Ha funcionado en
> el equipo de desarrollo (Windows 11), pero no hay ninguna garantía de que
> este driver funcione en tu PC. En caso de problemas, consulta el sitio web
> de Valeton (https://www.valeton.net) o los foros de usuarios del GP-180.

### Cambiar de idioma

Usa el menú desplegable de idioma en la parte superior. El cambio es inmediato
y persiste entre sesiones. Idiomas disponibles: francés, inglés, español.

### Configurar las claves API y la carpeta de salida

Menú **⚙ Config** en la parte superior derecha:
- **Claves API**: diálogo de configuración para todos los proveedores
- **Carpeta de salida**: abre la carpeta actual en el explorador de archivos


## Enviar presets al GP-180

Usa el botón **🔌 Inyectar** en la parte inferior derecha: el preset seleccionado
se envía directamente al slot configurado (📍) mediante USB SysEx. Este es el
único método de transferencia compatible con GP-180 Studio.


## Seguimiento de consumo

Si usas un proveedor de pago (Claude, OpenAI, Perplexity), la aplicación
muestra una estimación del costo de cada generación. Este seguimiento es una
estimación local — verifica tu saldo real en el sitio web del proveedor.

Puedes definir un límite de gasto en `config.json` (`budget_usd`).

Gemini (Google) no proporciona datos de consumo del lado del cliente:
el seguimiento de costos no está disponible para este proveedor.


## Problemas comunes

| Síntoma | Solución |
|---------|----------|
| *"Clave API inválida"* | Verifica la clave (sin espacios al inicio/final) y el proveedor seleccionado |
| *"Modelo no reconocido"* | La IA alucinó un nombre — reformula tu descripción |
| GP-180 no detectado (LED gris) | Verifica el cable USB y que el driver de Valeton esté instalado |
| Inyección fallida | Desconecta/reconecta el GP-180 y vuelve a intentarlo |
| Batch: no se mide sonido | Verifica que el driver USB Audio de Valeton esté instalado y que la entrada de audio apunte a *Línea (Valeton GP-180)* |
| Batch: `sounddevice` no encontrado | `pip install sounddevice pyloudnorm` |
| La aplicación no arranca | Verifica Python en el PATH (`python --version`) y Tkinter (`python -c "import tkinter"`) |
| Error de red / timeout | Verifica tu conexión a internet y que el proveedor de IA esté accesible |
| La cadena se muestra en varias filas | La ventana es demasiado estrecha — amplíala o pon a pantalla completa |
| La interfaz parece demasiado grande o pequeña | Se ajusta a la resolución de tu pantalla al arrancar. Reinicia tras un cambio de resolución o de escala en Windows. |

> **Nota**: la interfaz solo tiene modo oscuro. El botón claro/oscuro de
> versiones anteriores ha sido eliminado.
