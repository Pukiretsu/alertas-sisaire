# Sistema de Validación y Alerta de Calidad del Aire 🌬️

Este proyecto consiste en una solución basada en **Python** diseñada para automatizar la captura, procesamiento y validación de datos de calidad del aire provenientes de una plataforma. El objetivo principal es proporcionar a las autoridades ambientales una herramienta técnica confiable para la declaración de alertas basadas en normativas de concentración de contaminantes.

## 📌 Descripción del Proyecto
La herramienta aborda el desafío de la falta de una API pública en la fuente de datos original, implementando un flujo completo de datos que va desde el web scraping avanzado hasta un motor de decisión lógica. El sistema distingue entre estaciones **manuales** y **automáticas**, aplicando cálculos de medias móviles y criterios de persistencia (regla del 75%) para minimizar falsos positivos y asegurar la precisión en las alertas ambientales.

---

## 🚀 Requerimientos del Sistema

### 1. Fase de Ingesta: Extracción y Normalización
Dado que la plataforma JSF no tiene API, el reto principal es el Web Scraping o la automatización de la captura de datos.

* **R. Funcional 1.1 (Scraping/Extracción):** Desarrollar un componente capaz de navegar la plataforma JSF, manejar sesiones y estados (`javax.faces.ViewState`) para extraer los datos de concentraciones.
* **R. Funcional 1.2 (Sincronización):** Implementar un programador de tareas (*scheduler*) que ejecute la extracción cada hora (para automáticas) y cada 24 horas (para manuales).
* **R. Funcional 1.3 (Persistencia Raw):** Almacenar los datos crudos en una base de datos (PostgreSQL recomendado) con marcas de tiempo (*timestamp*), ID de estación y tipo de contaminante.
* **R. Técnico 1.4:** Implementar manejo de errores y reintentos en caso de que la plataforma JSF esté caída o cambie su estructura DOM.

### 2. Fase de Motor de Cálculo: Lógica de Umbrales
Esta fase transforma los datos crudos en métricas comparables.

* **R. Funcional 2.1 (Cálculo Media Móvil):** Para estaciones automáticas, calcular la media móvil de las últimas 24 horas cada vez que ingrese un nuevo dato.
* **R. Funcional 2.2 (Validación de Completitud):** Definir reglas para el cálculo de la media (ej. si falta más del 25% de los datos en las 24 horas, el cálculo se marca como inválido).
* **R. Funcional 2.3 (Identificación de Eventos):** Comparar el dato (directo en manuales, media móvil en automáticas) contra los umbrales normativos para disparar el estado de **"Seguimiento"**.
* **R. Técnico 2.4:** Utilizar librerías de análisis de datos como `pandas` o `numpy` para asegurar precisión y velocidad en los cálculos vectorizados.

### 3. Fase de Monitoreo y Alertas: Gestión de Estados
Esta es la capa de inteligencia que decide si se declara o no la alerta oficial.

* **R. Funcional 3.1 (Máquina de Estados):** Implementar la lógica de transición de estados: `Normal` ⮕ `Seguimiento` ⮕ `Prevención` ⮕ `Alerta` ⮕ `Emergencia` ⮕ `Finalizada`.
* **R. Funcional 3.2 (Regla del 75%):**
    * **Automáticas:** Evaluar la ventana de 48 horas posteriores al inicio del seguimiento. Si el 75% de las medias móviles superan el umbral, cambiar a estado Alerta.
    * **Manuales:** Evaluar los siguientes 3 datos reportados. Si en el 75% del tiempo (2 de cada 3 datos) se mantiene por encima, declarar la alerta.
* **R. Funcional 3.3 (Cierre de Alerta):** Definir el criterio de desescalamiento (cuando el dato cae por debajo del umbral durante un periodo determinado).
* **R. Funcional 3.4 (Dashboard/Notificación):** Generar una interfaz o servicio de mensajería (Email/Telegram) que notifique a las autoridades cuando una alerta sea validada.



---

## 🛠️ Instalación y Configuración del Entorno

Sigue estos pasos detallados para configurar tu espacio de trabajo local.

### 0. Requisitos previos.
Para poder ejecutar el proyecto es necesario instalar
- Python +3.10 [https://www.python.org/](https://www.python.org/)
- git [https://git-scm.com/](https://git-scm.com/)

### 1. Clonar el Repositorio
Obtén la última versión del código fuente desde el servidor:
```bash
git clone [https://github.com/tu-usuario/nombre-del-proyecto.git](https://github.com/tu-usuario/nombre-del-proyecto.git)
cd nombre-del-proyecto
```

### 2. Crear el entorno virtual
Utilizaremos `venv` para aislar las librerías del proyecto y evitar conflictos con el sistema:
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias
Una vez activado el entorno virtual (verás el prefijo (venv) en tu terminal), instala los paquetes necesarios:
```bash
python -m venv venv
venv\Scripts\activate
```
