import os
import logging
from typing import Optional

from google.cloud.firestore_v1 import AsyncClient

logger = logging.getLogger(__name__)


class FirestoreDB:
    """
    Helper wrapper that encapsulates the creation of a Firestore
    :class:`google.cloud.firestore_v1.AsyncClient`.

    The same object can transparently connect to:

    * **A local Firestore emulator** – useful for local development and CI.
    * **The real Firestore backend** – default when no emulator host is set.
    * **A mocked client** – handy for unit‐tests that must not touch the network.

    The public API intentionally stays minimal: configure once in ``__init__`` and,
    if needed, toggle the emulator or a mock with the provided helper methods.
    """

    def __init__(
        self,
        project_id: str,
        database: str | None = None,
        credentials=None,
        emulator_host: Optional[str] = None,
    ):
        """
        Parameters
        ----------
        project_id :
            Google Cloud project identifier (e.g. ``"my‐gcp‐project"``).
        database :
            Optional Firestore **database ID** (defaults to the default database).
        credentials :
            Explicit credentials object; if *None*, the Google SDK default
            credentials chain is used.
        emulator_host :
            Hostname (and port) of a running **Firestore emulator**
            such as ``"localhost:8080"``.  When provided, the client points
            to the emulator instead of the production service.
        """
        self.project_id = project_id
        self.database = database
        self.credentials = credentials
        self._emulator_host = emulator_host

        # Lazily create the AsyncClient
        self.client: AsyncClient = self._init_client()

    # --------------------------------------------------------------------- #
    # Internal helpers                                                      #
    # --------------------------------------------------------------------- #

    def _init_client(self) -> AsyncClient:
        """
        Instantiate and return an :class:`AsyncClient`.

        * If ``self._emulator_host`` is set, the mandatory
          ``FIRESTORE_EMULATOR_HOST`` environment variable is exported so that
          the Google client libraries route all traffic to the local emulator.
        * Otherwise, any previously set ``FIRESTORE_EMULATOR_HOST`` variable is
          removed to make sure we hit the real Firestore backend.
        """
        if self._emulator_host:
            os.environ["FIRESTORE_EMULATOR_HOST"] = self._emulator_host
            logger.info(f"Using Firestore emulator on {self._emulator_host}")
            return AsyncClient(
                project=self.project_id,
                database=self.database,
                credentials=self.credentials,
            )
        # -- Production (remote) Firestore --------------------------------- #
        os.environ.pop("FIRESTORE_EMULATOR_HOST", None)
        return AsyncClient(
            project=self.project_id,
            database=self.database,
            credentials=self.credentials,
        )

    # --------------------------------------------------------------------- #
    # Public utility methods                                                #
    # --------------------------------------------------------------------- #

    def use_emulator(self, host: str = "localhost:8080"):
        """
        Switch the instance to a **local emulator** and recreate the client.

        Call this at runtime if you need to toggle from production to emulator,
        for example in integration tests.

        Parameters
        ----------
        host :
            Target host and port where the emulator is listening.
        """
        self._emulator_host = host
        self.client = self._init_client()
        logger.info(f"Emulator enabled on {host}")

    def clear_emulator(self):
        """
        Disable the emulator and reconnect to the **production** Firestore
        endpoint.  A fresh :class:`AsyncClient` is created automatically.
        """
        self._emulator_host = None
        self.client = self._init_client()
        logger.info("Emulator disabled – using real Firestore.")

    def mock_firestore_for_tests(self):
        """
        Replace the underlying client with a :class:`unittest.mock.MagicMock`.

        This is the quickest way to isolate unit tests from Firestore without
        having to spin up the emulator or touch the network.
        """
        from unittest.mock import MagicMock

        self.client = MagicMock()
        logger.info("Firestore client replaced with MagicMock for unit tests.")
