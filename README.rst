Firestore Pydantic ODM
======================

**Firestore Pydantic ODM** es una librería para interactuar con Google
Cloud Firestore de forma sencilla y eficiente. Utiliza
`Pydantic <https://pydantic-docs.helpmanual.io/>`__ para la validación y
serialización de datos y ofrece soporte para operaciones asíncronas,
batch writes, transacciones, paginación, proyecciones y más.

Esta librería está diseñada para facilitar el desarrollo de aplicaciones
que requieren almacenar y consultar datos en Firestore, ofreciendo una
interfaz Pythonic y desacoplada que permite cambiar fácilmente el
cliente (por ejemplo, para usar emuladores o mocks en testing).

Características
---------------

-  **CRUD Asíncrono:** Soporte completo para crear, leer, actualizar y
   eliminar documentos de Firestore usando ``async/await``.
-  **Validación con Pydantic:** Define tus modelos de datos con
   validación automática, asegurando la integridad de la información.
-  **Consultas Avanzadas:** Realiza búsquedas con filtros, proyecciones
   (seleccionar solo ciertos campos) y ordenación.
-  **Batch Operations y Transacciones:** Agrupa múltiples operaciones de
   escritura y ejecuta transacciones de forma atómica para mayor
   eficiencia y coherencia.
-  **Soporte para Emulador y Testing:** Configura de forma sencilla el
   uso del emulador de Firestore o integra mocks para pruebas unitarias.
-  **Fácil Integración:** Se integra sin problemas en cualquier proyecto
   Python.

Instalación
-----------

Desde el Código Fuente
~~~~~~~~~~~~~~~~~~~~~~

1. Clona el repositorio:

   .. code:: bash

      git clone https://github.com/santosdevco/firestore-pydantic-odm
      cd firestore_pydantic_odm

2. Instala las dependencias y el paquete en modo editable:

   .. code:: bash

      pip install -e .

Dependencias
~~~~~~~~~~~~

Revisa el archivo `requirements.txt <requirements.txt>`__ para conocer
las dependencias necesarias, entre las que se incluyen: - ``pydantic`` -
``google-cloud-firestore>=2.0.0`` - ``pytest`` y ``pytest-asyncio``
(para testing)

Estructura del Proyecto
-----------------------

La organización recomendada es la siguiente:

::

   firestore_pydantic_odm/
       __init__.py         # Exposición de la API pública
       firestore_model.py  # Lógica principal del ODM
       firestore_fields.py # Descriptores y manejo de filtros
       enums.py            # Enumeraciones (e.g., BatchOperation)
       firestore_client.py # Inicialización y gestión del cliente Firestore
   tests/
       conftest.py         # Fixtures para pruebas
       tests.py            # Pruebas unitarias
   Dockerfile              # Configuración Docker
   docker-compose.yaml     # Configuración Docker Compose
   requirements.txt        # Dependencias del proyecto
   pytest.ini              # Configuración global de Pytest
   setup.py                # Script de instalación del paquete

..

   **Nota:** El archivo ``__init__.py`` es fundamental para que Python
   reconozca el directorio ``firestore_pydantic_odm`` como un paquete.
   En él se exportan las clases y funciones principales de la librería.

Uso Básico
----------

Definir un Modelo
~~~~~~~~~~~~~~~~~

Crea tus modelos extendiendo la clase base ``BaseFirestoreModel``:

.. code:: python

   from firestore_pydantic_odm import BaseFirestoreModel

   class User(BaseFirestoreModel):
       class Settings:
           name = "users"  # Nombre de la colección en Firestore

       name: str
       email: str

Inicializar el Cliente de Firestore
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Antes de utilizar los modelos, inicializa la conexión:

.. code:: python

   from firestore_pydantic_odm import FirestoreDB, BaseFirestoreModel

   # Inicializa el cliente, pudiendo especificar el host del emulador si es necesario
   db = FirestoreDB(project_id="tu-proyecto", emulator_host="localhost:8080")

   # Inyecta el cliente en la clase base para que todos los modelos lo utilicen
   BaseFirestoreModel.initialize_db(db)

Operaciones CRUD
~~~~~~~~~~~~~~~~

Crear y Guardar un Documento
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   user = User(name="Alice", email="alice@example.com")
   await user.save()

Actualizar un Documento
^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   user.email = "nueva_alice@example.com"
   await user.update()

Eliminar un Documento
^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   await user.delete()

Obtener un Documento por ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   user = await User.get("id_del_documento")

Consultas
~~~~~~~~~

Buscar Documentos
^^^^^^^^^^^^^^^^^

Realiza búsquedas utilizando filtros:

.. code:: python

   async for user in User.find(filters=[User.name == "Alice"]):
       print(user)

Buscar un Único Documento
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   user = await User.find_one(filters=[User.email ==  "alice@example.com"])

Usar Proyecciones
^^^^^^^^^^^^^^^^^

Si solo necesitas ciertos campos, puedes usar un modelo de proyección:

.. code:: python

   from pydantic import BaseModel

   class UserProjection(BaseModel):
       name: str

   async for user in User.find(filters=[User.name ==  "Alice"], projection=UserProjection):
       print(user)

Batch Operations y Transacciones
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Operaciones en Batch
^^^^^^^^^^^^^^^^^^^^

.. code:: python

   from firestore_pydantic_odm import BatchOperation

   ops = [
       (BatchOperation.CREATE, User(name="Bob", email="bob@example.com")),
       (BatchOperation.UPDATE, user),
       (BatchOperation.DELETE, another_user)
   ]

   await User.batch_write(ops)

Testing
-------

| El proyecto incluye pruebas unitarias con
  `pytest <https://docs.pytest.org/>`__ y
  `pytest-asyncio <https://github.com/pytest-dev/pytest-asyncio>`__.
| Para ejecutar los tests, simplemente corre:

.. code:: bash

   pytest

El archivo ``pytest.ini`` y ``conftest.py`` (ubicado en la raíz o en el
directorio ``tests/``) proporcionan la configuración y las fixtures
necesarias.

Contribuir
----------

¡Contribuciones son bienvenidas! Si deseas aportar mejoras:

1. Haz un fork del repositorio.
2. Crea una rama para tu feature o corrección.
3. Realiza tus cambios y asegúrate de que todos los tests pasen.
4. Envía un Pull Request describiendo tus mejoras.

Licencia
--------

Distribuido bajo la Licencia MIT. Consulta el archivo
`LICENSE <LICENSE>`__ para más detalles.
