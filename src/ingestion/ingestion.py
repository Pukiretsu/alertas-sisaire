import logging
import re, urllib
from os import path
import time
from playwright.sync_api import sync_playwright
from src.utils.configs import Config

logger = logging.getLogger(__name__)


class SISAIREscrapper:
    def __init__(self, headless=True) -> None:
        self.headless = headless
    
    def block_irrelevant_content(self, context):
        """Bloquea imágenes y otros recursos innecesarios para acelerar la carga."""
        def interceptar(route):
            recursos_ignorar = ["image", "font", "media"]
            
            if route.request.resource_type in recursos_ignorar:
                logger.debug(f"Bloqueando carga de: {route.request.url}")
                route.abort()
            else:
                route.continue_()

        context.route("**/*", interceptar)
    
    def activar_traza_red(self, page):
        """Monitorea y loguea todas las peticiones POST (AJAX/Fetch)."""
    
        def on_request(request):
            if request.method == "POST":
                print(f"\n🚀 [POST] -> {request.url}")
                post_data = request.post_data
                if post_data:
                    match = re.search(r'javax\.faces\.ViewState=([^&]+)', post_data)
                    
                    if match:
                        view_state_encoded = match.group(1)
                        view_state_decoded = urllib.parse.unquote(view_state_encoded)
                        print(f"    🔑 ViewState en Payload: {view_state_decoded}")
                    else:
                        print("    ⚠️ No se encontró ViewState en el Payload.")

        def on_response(response):
            if response.request.method == "POST":
                status = response.status
                print(f"✅ [RES] <- Status: {status} para {response.url}")

        page.on("request", on_request)
        page.on("response", on_response)

    def get_departamentos(self, page):
        logger.info("Extrayendo lista de departamentos...")
    
        selector_dropdown = 'div[id="filtroForm:departamentoSel"]'
        page.click(selector_dropdown)
    
        selector_lista = 'ul[id="filtroForm:departamentoSel_items"]'
        page.wait_for_selector(selector_lista, state="visible")

        departamentos = page.locator(f"{selector_lista} li").evaluate_all("""
            elements => elements.map(el => ({
                "nombre": el.getAttribute('data-label'),
                "id_interno": el.id
            }))
        """)

        departamentos = [d for d in departamentos if d['nombre'] != 'Todos']
    
        logger.info(f"Se encontraron {len(departamentos)} departamentos.")
        return departamentos

    def start_scrapping(self):
        with sync_playwright() as p:
            browser_path = "/usr/bin/chromium"
  
            logger.info("lanzando el navegador")
            browser = p.chromium.launch(
                headless=False,
                executable_path=browser_path if path.exists(browser_path) else None,
            )

            context = browser.new_context()
            context.set_default_timeout(120000)
            
            self.block_irrelevant_content(context)
            page = context.new_page()
            self.activar_traza_red(page)

            try:
                target_url = Config.JSF_TARGET_URL
                time.sleep(3)

                logger.info(f"Navegando en {target_url}")
                
                page.goto(target_url, wait_until="networkidle") 
                page.wait_for_function("() => PrimeFaces.ajax.Queue.isEmpty()", timeout=120000)
                
                logger.debug("Pagina cargada")
                
                deptos = self.get_departamentos(page)
                print(deptos)
                
                selector_dropdown = 'li[id="filtroForm:departamentoSel_5"]'
                page.click(selector_dropdown)

                page.wait_for_function("() => PrimeFaces.ajax.Queue.isEmpty()", timeout=120000)
                logger.debug('Departamento seleccionado')

                time.sleep(5)

            except Exception as e:
                logger.error(f"Error en la navegación: {e}")

            finally:
                browser.close()


if __name__ == "__main__":
    logger.info("Modo de prueba local del Scrapper iniciado...")

    scrapper = SISAIREscrapper(headless=False)
    result = scrapper.start_scrapping()
