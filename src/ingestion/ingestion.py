import logging
import os
from playwright.sync_api import sync_playwright
from src.utils.configs import Config

# Configuración de logging
logger = logging.getLogger(__name__)

class SISAIREscrapper:
    """
    Scraper para la plataforma SISAIRE que automatiza la extracción de datos
    de calidad del aire mediante Playwright.
    """

    def __init__(self, ids_estaciones, contaminante, fecha_ini, fecha_fin, ruta, filename, headless=True):
        """
        Args:
            ids_estaciones (list): Lista de IDs (strings) de las estaciones a consultar.
            contaminante (str): Nombre del contaminante (ej. 'PM2.5').
            fecha_ini (str): Fecha de inicio en formato YYYY-MM-DD.
            fecha_fin (str): Fecha de fin en formato YYYY-MM-DD.
            ruta (str): Directorio donde se guardará el archivo.
            filename (str): Nombre base para el archivo descargado.
            headless (bool): Indica si el navegador se ejecuta sin interfaz gráfica.
        """
        self.headless = headless
        self.ids_estaciones_consulta = ids_estaciones
        self.contaminante = contaminante
        self.fecha_inicio = fecha_ini
        self.fecha_fin = fecha_fin
        self.ruta = ruta
        self.filename = filename

    def block_irrelevant_content(self, context):
        """
        Intercepta peticiones de red para bloquear recursos pesados (imágenes, fuentes)
        y acelerar el tiempo de carga de la página.
        """
        recursos_ignorar = ["image", "font", "media"]

        def interceptar(route):
            if route.request.resource_type in recursos_ignorar:
                route.abort()
            else:
                route.continue_()

        context.route("**/*", interceptar)

    def wait_until_loaded(self, page):
        """
        Espera a que los spinners de PrimeFaces desaparezcan y la cola AJAX esté vacía.
        """
        page.wait_for_timeout(300)
        
        # Esperar a que los indicadores de carga se oculten
        for selector in ['i[id="loading"]', 'i[id="loadingResults"]']:
            locator = page.locator(selector)
            if locator.is_visible():
                locator.wait_for(state="hidden", timeout=30000)
        
        # Sincronización con el motor de PrimeFaces
        js_check = "() => typeof PrimeFaces !== 'undefined' && PrimeFaces.ajax.Queue.isEmpty()"
        page.wait_for_function(js_check, timeout=60000)

    def select_estaciones(self, page):
        """Abre el dropdown de estaciones y marca los checkboxes correspondientes."""
        self.wait_until_loaded(page)

        selector_dropdown = 'div[id="filtroForm:estacionesSel"]'
        page.click(selector_dropdown)
        
        panel = page.locator('div[id="filtroForm:estacionesSel_panel"]')
        panel.wait_for(state="visible")

        for estacion_id in self.ids_estaciones_consulta:
            selector_item = panel.locator(f'li[data-item-value="{estacion_id}"]')
            # Click directo en el checkbox dentro del item de la lista
            selector_item.locator(".ui-chkbox-box").click()
        
        # Cerrar el dropdown clickeando fuera o en el mismo toggle
        page.click(selector_dropdown)
        logger.info(f"Seleccionadas {len(self.ids_estaciones_consulta)} estaciones.")
        self.wait_until_loaded(page)

    def select_contaminantes(self, page):
        """Selecciona el contaminante del menú desplegable."""
        if not self.contaminante:
            return
        
        selector_dropdown = 'div[id="filtroForm:contaminanteSel"]'
        page.locator(selector_dropdown).click()
    
        panel = page.locator('div[id="filtroForm:contaminanteSel_panel"]')
        panel.wait_for(state="visible")

        item = panel.locator(f'li[data-label="{self.contaminante}"]')
        item.wait_for(state="visible")
        item.click()
        
        self.wait_until_loaded(page)

    def select_fechas(self, page):
        """Completa los inputs de fecha de inicio y fin confirmando con Tab."""
        self.wait_until_loaded(page)
        
        config_fechas = [
            ('input[id="filtroForm:fechaIni_input"]', self.fecha_inicio),
            ('input[id="filtroForm:fechaFin_input"]', self.fecha_fin)
        ]
        
        for selector, valor in config_fechas:
            input_el = page.locator(selector)
            input_el.click()
            input_el.fill("")  # Limpia el campo
            input_el.press_sequentially(valor, delay=50)
            input_el.press("Tab")  # Cierra el datepicker y valida
            page.wait_for_timeout(300)

        self.wait_until_loaded(page)

    def select_timeframe(self, page):
        """Selecciona el tipo de resolución temporal (horario/diario)."""
        self.wait_until_loaded(page)
        
        page.click('div[id="filtroForm:tipoSel"]')
        panel = page.locator('div[id="filtroForm:tipoSel_panel"]')
        panel.wait_for(state="visible")
        
        # Selecciona la opción 1 (comúnmente resolución horaria)
        panel.locator('li[id="filtroForm:tipoSel_1"]').click()
        self.wait_until_loaded(page)

    def download_csv(self, page):
        """Gestiona la descarga del archivo CSV y lo renombra."""
        os.makedirs(self.ruta, exist_ok=True)
        selector_csv = 'a .fa-file-text-o'
        
        try:
            with page.expect_download(timeout=60000) as download_info:
                page.locator(selector_csv).click()

            download = download_info.value
            ruta_destino = os.path.join(self.ruta, f"reporte-{self.filename}.csv")
            
            logger.info(f"Descargando: {download.suggested_filename}")
            download.save_as(ruta_destino)
            logger.info(f"Éxito: Guardado en {ruta_destino}")
        except Exception as e:
            logger.error(f"Fallo en la descarga: {e}")

    def start_scrapping(self):
        """Inicia el proceso completo de scraping."""
        with sync_playwright() as p:
            # Configuración dinámica del ejecutable
            exec_path = "/usr/bin/chromium"
            browser_args = {
                "headless": self.headless,
                "executable_path": exec_path if os.path.exists(exec_path) else None
            }

            logger.info("Iniciando navegador...")
            browser = p.chromium.launch(**browser_args)
            context = browser.new_context()
            context.set_default_timeout(120000)
            
            self.block_irrelevant_content(context)
            page = context.new_page()

            try:
                target_url = Config.JSF_TARGET_URL
                logger.info(f"Navegando a: {target_url}")
                
                page.goto(target_url, wait_until="networkidle") 
                self.wait_until_loaded(page)

                self.select_estaciones(page)
                logger.info(f"Contaminante: {self.contaminante}")
                self.select_contaminantes(page)
                
                logger.info(f"Rango: {self.fecha_inicio} a {self.fecha_fin}")
                self.select_fechas(page)
                self.select_timeframe(page)

                # Consultar y descargar
                page.click('button[id="filtroForm:btnConsultar"]')
                self.wait_until_loaded(page)
                self.download_csv(page)

            except Exception as e:
                logger.error(f"Error durante la ejecución: {e}", exc_info=True)
            finally:
                browser.close()
                logger.info("Navegador cerrado.")

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

    scrapper = SISAIREscrapper(
        ids_estaciones=ids_estaciones_consulta,
        contaminante="PM2.5",
        fecha_ini="2023-01-01",
        fecha_fin="2023-01-02",
        ruta="./data",
        filename="TEST_REFAC",
        headless=False
    )
    scrapper.start_scrapping()
