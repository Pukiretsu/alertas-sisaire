import logging
import re, urllib
from os import path, wait
import time
from playwright.sync_api import sync_playwright
from src.utils.configs import Config

logger = logging.getLogger(__name__)

class SISAIREscrapper:
    def __init__(self, ids_estaciones_consulta, contaminante, fecha_inicio, fecha_fin, headless=True) -> None:
        self.headless = headless
        self.ids_estaciones_consulta = ids_estaciones_consulta
        self.contaminante = contaminante
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin

    def block_irrelevant_content(self, context):
        """Bloquea imágenes y otros recursos innecesarios para acelerar la carga."""
        def interceptar(route):
            recursos_ignorar = ["image", "font", "media"]
            
            if route.request.resource_type in recursos_ignorar:
                #logger.debug(f"Bloqueando carga de: {route.request.url}")
                route.abort()
            else:
                route.continue_()

        context.route("**/*", interceptar)

    def wait_until_loaded(self, page):
        page.wait_for_function("() => PrimeFaces.ajax.Queue.isEmpty()", timeout=120000)

    def select_estaciones(self, page):
        selector_dropdown = 'div[id="filtroForm:estacionesSel"]'
        page.click(selector_dropdown)
        
        selector_panel = 'div[id="filtroForm:estacionesSel_panel"]'
        page.wait_for_selector(selector_panel, state="visible")

        for estacion_id in self.ids_estaciones_consulta:
            selector_estacion = page.locator(f'li[data-item-value="{estacion_id}"]')
            checkbox = selector_estacion.locator(".ui-chkbox-box")
            checkbox.click()
        
        page.click(selector_dropdown)
        logger.info(f"{len(self.ids_estaciones_consulta)} Estaciones seleccionadas...")
    
    def select_contaminantes(self, page):
        selector_dropdown = 'div[id="filtroForm:contaminanteSel"]'
        page.click(selector_dropdown)
        
        selector_panel = 'div[id="filtroForm:contaminanteSel_panel"]'
        page.wait_for_selector(selector_panel, state="visible")

        selector_contaminante = page.locator(f'ul[id="filtroForm:contaminanteSel_items"]')
        if not self.contaminante:
            return
        else:
            item_contaminante = selector_contaminante.locator(f'li[data-label="{self.contaminante}"]')
            item_contaminante.click()
        
        page.click(selector_dropdown)

    def select_fechas(self, page):
        pass

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

            try:
                target_url = Config.JSF_TARGET_URL
                time.sleep(3)

                logger.info(f"Navegando en {target_url}")
                
                page.goto(target_url, wait_until="networkidle") 
                self.wait_until_loaded(page)
                logger.info("Pagina cargada")
                
                logger.debug("Seleccionando estaciones")
                self.select_estaciones(page)
                self.wait_until_loaded(page)
                
                if not self.contaminante:
                    logger.info("Seleccionando todos los contaminantes")
                else:
                    logger.info(f"Seleccionando Contaminante: {self.contaminante}")
                    self.select_contaminantes(page)
                    self.wait_until_loaded(page)
                
                logger.info(f"Seleccionando datos desde {self.fecha_inicio} hasta {self.fecha_fin}")
                self.select_fechas(page)
                self.wait_until_loaded(page)
                time.sleep(20)
                
                selector_button = 'button[id="filtroForm:btnConsultar"]'
                page.click(selector_button)
                self.wait_until_loaded(page)
                logger.info("Pagina cargada completamente...")

                time.sleep(60)

            except Exception as e:
                logger.error(f"Error en la navegación: {e}")

            finally:
                browser.close()


if __name__ == "__main__":
    logger.info("Modo de prueba local del Scrapper iniciado...")
    
    ids_estaciones_consulta = [
        "29586", "31877", "8249", "31862", "8254", "8243", 
        "31867", "31866", "31865", "31860", "31869", "31805", 
        "31807", "31863", "31864", "29617", "30040", "32089", 
        "31953", "31870", "8250", "31952", "8252"
    ]
    
    contaminante = "PM2.5"

    fecha_inicio = "2023-01-01"
    fecha_fin = "2023-01-02"

    scrapper = SISAIREscrapper(ids_estaciones_consulta, contaminante,fecha_inicio, fecha_fin, headless=False)
    result = scrapper.start_scrapping()
