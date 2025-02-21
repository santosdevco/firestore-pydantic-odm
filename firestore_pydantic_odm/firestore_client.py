import os
import logging
from typing import Optional

from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)

class FirestoreDB:
    """
    Clase que maneja la inicialización del cliente de Firestore.
    Permite usar el emulador local, un cliente real o un mock.
    """
    def __init__(self, project_id: str,database:str=None, credentials=None, emulator_host: Optional[str] = None):
        """
        :param project_id: ID de proyecto de GCP.
        :param credentials: Credenciales (pueden ser None si usas valores por defecto).
        :param emulator_host: (Opcional) Host de emulador, p.e. "localhost:8080".
        """
        self.project_id = project_id
        self.database = database    
        self.credentials = credentials
        self._emulator_host = emulator_host
        # Inicializamos el cliente
        self.client = self._init_client()

    def _init_client(self) -> AsyncClient:
        """
        Inicializa el cliente de Firestore con o sin emulador.
        """
        if self._emulator_host:
            os.environ["FIRESTORE_EMULATOR_HOST"] = self._emulator_host
            logger.info(f"Usando emulador de Firestore en {self._emulator_host}")
            return AsyncClient(
                project=self.project_id, 
                database=self.database,
                credentials=self.credentials,
                # host=self._emulator_host
            )
        else:
            # Si no se provee emulador, eliminamos la variable (en caso de que exista).
            if "FIRESTORE_EMULATOR_HOST" in os.environ:
                del os.environ["FIRESTORE_EMULATOR_HOST"]
            return AsyncClient(
                project=self.project_id, 
                database=self.database,
                credentials=self.credentials
            )

    def use_emulator(self, host: str = "localhost:8080"):
        """
        Fuerza el uso del emulador de Firestore (reinicia el cliente).
        """
        self._emulator_host = host
        self.client = self._init_client()
        logger.info(f"Emulador activado en {host}")

    def clear_emulator(self):
        """
        Deja de usar el emulador y apunta a Firestore real (reinicia el cliente).
        """
        self._emulator_host = None
        self.client = self._init_client()
        logger.info("Emulador desactivado. Usando Firestore real.")

    def mock_firestore_for_tests(self):
        """
        Reemplaza el cliente real con un mock (MagicMock),
        para pruebas unitarias sin conectar a Firestore real.
        """
        from unittest.mock import MagicMock

        self.client = MagicMock()
        logger.info("Firestore mockeado para pruebas unitarias.")
