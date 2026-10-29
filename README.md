# DSL de reglas de descuento: Etapa 1

Aplicación web (Flask) con el enunciado del proyecto, un bloque para escribir o subir
el lenguaje (con un ejemplo precargado) y la generación de **tokens y lexemas**.

## Contenido

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Aplicación Flask (enunciado, entrada de texto/archivo, resultado) |
| `lexer.py` | Analizador léxico: especificación de tokens y algoritmo de reconocimiento |
| `templates/index.html` | Página de la aplicación Flask (HTML) |
| `static/style.css` | Estilos de la página |
| `static/script.js` | Comportamiento en el navegador (restaurar ejemplo, limpiar, nombre del archivo) |
| `requirements.txt` | Dependencias que el hosting instala (Flask y gunicorn) |
| `Procfile` | Comando de arranque para hostings que lo leen: `web: gunicorn app:app` |

## Ejecutar en tu computadora

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate        Linux/Mac:  source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Abre http://127.0.0.1:5000. Para desarrollo con recarga automática: `flask --app app --debug run`.

## Paso 1.1: Hola Mundo en GitHub Pages

1. Crea un repositorio en GitHub y súbele el proyecto:
   ```bash
   git init
   git add .
   git commit -m "Etapa 1"
   git branch -M main
   git remote add origin https://github.com/USUARIO/REPOSITORIO.git
   git push -u origin main
   ```
2. En GitHub: **Settings → Pages → Source: Deploy from a branch → Branch: `main` / carpeta `/docs` → Save**.
3. A los pocos minutos queda publicado en `https://USUARIO.github.io/REPOSITORIO/`.

GitHub Pages solo sirve páginas estáticas, así que publica el Hola Mundo (`docs/index.html`).
La aplicación Flask necesita un hosting que ejecute Python (paso siguiente).

## Paso 1.3: Publicar la aplicación Flask (hosting gratuito)

Los planes gratuitos cambian con el tiempo; confirma las condiciones vigentes antes de elegir.

El archivo se llama exactamente `Procfile` (P mayúscula, sin extensión; en Windows cuida que el
Bloc de notas no lo guarde como `Procfile.txt`). Significa: `gunicorn` arranca el objeto `app` que
está en el archivo `app.py`. No todos los hostings lo leen:

| Hosting | Cómo arranca la app |
|---|---|
| Render | Comando de inicio escrito en su panel (`gunicorn app:app`) |


**Opción A: Render** (recomendada: se conecta al repositorio de GitHub y se actualiza con cada `git push`)

1. Crea una cuenta en Render e inicia sesión con GitHub.
2. **New → Web Service** y conecta el repositorio del proyecto.
3. *Build command*: `pip install -r requirements.txt`
4. *Start command*: `gunicorn app:app`
5. Elige el plan **Free** y crea el servicio.

El plan gratuito suspende el servicio tras 15 minutos sin visitas, y la primera carga después
de eso tarda cerca de un minuto. Abre la URL unos minutos antes de una presentación.

**Opción B: PythonAnywhere** (pensado para Python; 1 aplicación web gratuita en `usuario.pythonanywhere.com`)

1. Crea una cuenta gratuita ("Beginner").
2. En una consola Bash: `git clone https://github.com/USUARIO/REPOSITORIO.git`
3. Pestaña **Web → Add a new web app → Manual configuration** (elige tu versión de Python).
4. En *Source code* pon `/home/USUARIO/REPOSITORIO`.
5. Abre el archivo WSGI que indica esa pestaña y reemplaza su contenido por:
   ```python
   import sys
   ruta = "/home/USUARIO/REPOSITORIO"
   if ruta not in sys.path:
       sys.path.insert(0, ruta)
   from app import app as application
   ```
6. Pulsa **Reload**.

Diferencias a tener en cuenta: la aplicación gratuita de PythonAnywhere indica 1 mes de caducidad,
así que hay que renovarla desde la pestaña **Web**, y las actualizaciones son manuales
(`git pull` en la consola y **Reload**).

## Qué hace el analizador

- Reconoce los 17 tokens del diseño: `T_SI`, `T_SINO`, `T_ENTONCES`, `T_APLICAR`, `T_DESCUENTO`,
  `T_AND`, `T_OR`, `T_NOT`, `T_TIEMPO`, `T_OBJETO`, `T_ID`, `T_NUM`, `T_PORCENTAJE`, `T_RELOP`,
  `T_PUNTO`, `T_PARI`, `T_PARD`.
- Las palabras reservadas distinguen mayúsculas (`SI` es reservada, `si` es un identificador).
- `SINO` es un solo token (coincidencia más larga) y `15%` es `T_PORCENTAJE`, no `T_NUM` + `%`.
- Un carácter fuera del alfabeto (por ejemplo `@` o un `!` suelto) se reporta como error léxico
  con línea y columna, y el análisis continúa.
- Acepta texto escrito o un archivo `.txt` en UTF-8 de hasta 100 KB.
