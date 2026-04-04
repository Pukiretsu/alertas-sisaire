import logging
import re, urllib
from os import path, makedirs
import time
from playwright.sync_api import sync_playwright
from src.utils.configs import Config

logger = logging.getLogger(__name__)

class SISAIREscrapper:
    def __init__(self, ids_estaciones_consulta, contaminante, fecha_inicio, fecha_fin, ruta, filename, headless=True) -> None:
        self.headless = headless
        self.ids_estaciones_consulta = ids_estaciones_consulta
        self.contaminante = contaminante
        self.fecha_inicio = fecha_inicio
        self.fecha_fin = fecha_fin
        self.ruta = ruta
        self.filename = filename

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
        page.wait_for_timeout(300)
        
        for selector in ['i[id="loading"]', 'i[id="loadingResults"]']:
            locator = page.locator(selector)
            if locator.is_visible():
                locator.wait_for(state="hidden", timeout=30000)
        
        page.wait_for_function("() => typeof PrimeFaces !== 'undefined' && PrimeFaces.ajax.Queue.isEmpty()", timeout=60000)

    def select_estaciones(self, page):
        self.wait_until_loaded(page)

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

        self.wait_until_loaded(page)
    
    def select_contaminantes(self, page):
        if not self.contaminante:
            return
        
        selector_dropdown = 'div[id="filtroForm:contaminanteSel"]'
        # Usamos click con scroll para asegurar impacto
        page.locator(selector_dropdown).click()
    
        # Esperamos a que el panel del contaminante sea visible
        selector_panel = 'div[id="filtroForm:contaminanteSel_panel"]'
        panel = page.locator(selector_panel)
        panel.wait_for(state="visible")

        # Seleccionar el item específico
        item_contaminante = panel.locator(f'li[data-label="{self.contaminante}"]')
    
        # A veces el item tarda un poco más que el panel
        item_contaminante.wait_for(state="visible")
        item_contaminante.click()
        
        page.locator(selector_dropdown).click()
        item_contaminante.click()
        
        # IMPORTANTE: Después de seleccionar, PrimeFaces suele disparar un AJAX
        self.wait_until_loaded(page)
        

    def select_fechas(self, page):
        self.wait_until_loaded(page)
        
        start_date_selector = 'input[id="filtroForm:fechaIni_input"]'
        end_date_selector = 'input[id="filtroForm:fechaFin_input"]'
        
        for selector, fecha in [(start_date_selector, self.fecha_inicio),
                                (end_date_selector, self.fecha_fin)]:
            input_element = page.locator(selector)
            input_element.click()
            
            input_element.wait_for(state="visible")
            input_element.fill("")

            input_element.press_sequentially(fecha, delay=50)
            input_element.press("Tab")

            page.wait_for_timeout(300)

        self.wait_until_loaded(page)
    
    def select_timeframe(self, page):
        self.wait_until_loaded(page)
        timeframe_selector = 'div[id="filtroForm:tipoSel"]'
        timeframe_panel_selector = 'div[id="filtroForm:tipoSel_panel"]'
        
        timeframe_element = page.locator(timeframe_selector)
        timeframe_element.click()

        timeframe_panel_element = page.locator(timeframe_panel_selector)
        timeframe_panel_element.wait_for(state="visible")
        
        timeframe_panel_selection = timeframe_panel_element.locator('li[id="filtroForm:tipoSel_1"]')
        timeframe_panel_selection.click()

        timeframe_element.click()

        self.wait_until_loaded(page)


    def download_csv(self, page):
        makedirs(path.dirname(self.ruta), exist_ok=True)

        selector_download_csv = 'a .fa-file-text-o'
        
        try:
            with page.expect_download(timeout=60000) as download_info:
                page.locator(selector_download_csv).click()

            download = download_info.value
            ruta_destino = path.join(self.ruta, f"reporte-{self.filename}.csv")
            name = download.suggested_filename
            logger.info(f"Descargando archivo: {name}")
            download.save_as(ruta_destino)
            logger.info(f"Archivo guardado en: {ruta_destino}")
        except Exception as e:
            logger.error(f"Error al descargar: {e}")

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

                logger.info(f"Navegando en {target_url}")
                
                page.goto(target_url, wait_until="networkidle") 
                self.wait_until_loaded(page)
                logger.info("Pagina cargada")
                
                logger.debug("Seleccionando estaciones")
                self.select_estaciones(page)
                
                logger.info(f"Seleccionando Contaminante: {self.contaminante}")
                self.select_contaminantes(page)
                
                logger.info(f"Seleccionando datos desde {self.fecha_inicio} hasta {self.fecha_fin}")
                self.select_fechas(page)
                
                self.select_timeframe(page)

                selector_button = 'button[id="filtroForm:btnConsultar"]'
                page.click(selector_button)
                self.wait_until_loaded(page)
                
                logger.info("Pagina cargada completamente...")

                self.download_csv(page)
                

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
    route = "./data"
    filename = "TEST"
    fecha_inicio = "2023-01-01"
    fecha_fin = "2023-01-02"

    scrapper = SISAIREscrapper(ids_estaciones_consulta, 
                               contaminante,
                               fecha_inicio, 
                               fecha_fin, 
                               route,
                               filename, 
                               headless=False)
    result = scrapper.start_scrapping()
