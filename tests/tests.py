import pytest
import pytest_asyncio
from unittest.mock import MagicMock, AsyncMock
from typing import Any, Tuple, List, Optional, Union, AsyncGenerator, Type

# Ajusta la ruta según tu estructura real.
from firestore_model import *

# -----------------------------------------------------------------------------
# 1. Modelo de ejemplo para pruebas
# -----------------------------------------------------------------------------
class User(BaseFirestoreModel):
    class Settings:
        name = "users"

    name: str
    email: str

# -----------------------------------------------------------------------------
# 2. Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
def mock_firestore_client():
    """Crea un MagicMock para el cliente de Firestore."""
    return MagicMock()

@pytest.fixture
def firestore_db(mock_firestore_client):
    """
    Crea la instancia de FirestoreDB usando un cliente mock.
    Se sobrescribe el atributo `client` con el mock.
    """
    db = FirestoreDB(project_id="test-project")
    db.client = mock_firestore_client
    return db

@pytest_asyncio.fixture
async def initialized_model(firestore_db):
    """
    Inyecta el objeto FirestoreDB en BaseFirestoreModel.
    Todos los modelos hijos usarán este cliente.
    """
    BaseFirestoreModel.initialize_db(firestore_db)
    return User

# -----------------------------------------------------------------------------
# 3. Pruebas de FirestoreDB
# -----------------------------------------------------------------------------
def test_firestore_db_init(firestore_db):
    assert firestore_db.project_id == "test-project"
    assert firestore_db.client is not None

def test_firestore_db_emulator(firestore_db):
    firestore_db.use_emulator("localhost:9090")
    # En este caso, _emulator_host se define exactamente con el string.
    assert firestore_db._emulator_host == "localhost:9090"
    firestore_db.clear_emulator()
    assert firestore_db._emulator_host is None

def test_firestore_db_mock(firestore_db):
    firestore_db.mock_firestore_for_tests()
    from unittest.mock import MagicMock
    assert isinstance(firestore_db.client, MagicMock)

# -----------------------------------------------------------------------------
# 4. Pruebas de modelo (CRUD)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_save_document(initialized_model):
    user = initialized_model(name="Alice", email="alice@example.com")
    
    # Simulamos un doc_ref con métodos asíncronos y un id.
    doc_ref_mock = MagicMock()
    doc_ref_mock.id = "mock_id"
    doc_ref_mock.set = AsyncMock()
    
    collection_ref_mock = MagicMock()
    collection_ref_mock.document.return_value = doc_ref_mock
    
    user._db.client.collection.return_value = collection_ref_mock

    saved_user = await user.save()
    
    collection_ref_mock.document.assert_called_once_with()
    doc_ref_mock.set.assert_awaited_once_with({
        "name": "Alice",
        "email": "alice@example.com"
    })
    assert saved_user.id == "mock_id"

@pytest.mark.asyncio
async def test_update_document(initialized_model):
    user = initialized_model(id="abc123", name="Alice", email="alice@example.com")
    
    doc_ref_mock = MagicMock()
    doc_ref_mock.update = AsyncMock()
    collection_ref_mock = MagicMock()
    collection_ref_mock.document.return_value = doc_ref_mock
    user._db.client.collection.return_value = collection_ref_mock

    await user.update()
    doc_ref_mock.update.assert_awaited_once_with({
        "name": "Alice",
        "email": "alice@example.com"
    })

@pytest.mark.asyncio
async def test_delete_document(initialized_model):
    user = initialized_model(id="abc123", name="Alice", email="alice@example.com")
    
    doc_ref_mock = MagicMock()
    doc_ref_mock.delete = AsyncMock()
    collection_ref_mock = MagicMock()
    collection_ref_mock.document.return_value = doc_ref_mock
    user._db.client.collection.return_value = collection_ref_mock

    await user.delete()
    doc_ref_mock.delete.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_document(initialized_model):
    # Simulamos un snapshot.
    doc_snap_mock = MagicMock()
    doc_snap_mock.exists = True
    doc_snap_mock.id = "abc123"
    doc_snap_mock.to_dict.return_value = {
        "name": "Alice",
        "email": "alice@example.com"
    }
    
    doc_ref_mock = MagicMock()
    doc_ref_mock.get = AsyncMock(return_value=doc_snap_mock)
    collection_ref_mock = MagicMock()
    collection_ref_mock.document.return_value = doc_ref_mock
    initialized_model._db.client.collection.return_value = collection_ref_mock

    user = await initialized_model.get("abc123")
    doc_ref_mock.get.assert_awaited_once()
    assert user is not None
    assert user.id == "abc123"
    assert user.name == "Alice"
    assert user.email == "alice@example.com"

# -----------------------------------------------------------------------------
# 5. Pruebas de count()
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_count_documents(initialized_model):
    """
    Simula que query.count() no está disponible y fuerza el fallback.
    """
    query_mock = MagicMock()
    # Forzamos que query.count() lance un AttributeError.
    query_mock.count = MagicMock(side_effect=AttributeError("No .count() method"))
    query_mock.get = AsyncMock(return_value=[MagicMock(), MagicMock(), MagicMock()])
    
    collection_ref_mock = MagicMock()
    collection_ref_mock.where.return_value = query_mock
    initialized_model._db.client.collection.return_value = collection_ref_mock

    total = await initialized_model.count([
        (str(initialized_model.name), "==", "Alice"),
    ])
    collection_ref_mock.where.assert_called_once_with(
        field_path="name", op_string="==", value="Alice"
    )
    assert total == 3

# -----------------------------------------------------------------------------
# 6. Pruebas de find() y find_one()
# -----------------------------------------------------------------------------
# Función auxiliar para un async generator.
async def mock_stream_generator(docs: List[Any]) -> AsyncGenerator[Any, None]:
    for doc in docs:
        print(doc)
        yield doc

@pytest.mark.asyncio
async def test_find_no_filters(initialized_model):
    # Creamos dos documentos simulados.
    doc_mock_1 = MagicMock()
    doc_mock_1.id = "doc1"
    doc_mock_1.to_dict.return_value = {"name": "Alice", "email": "alice@example.com"}

    doc_mock_2 = MagicMock()
    doc_mock_2.id = "doc2"
    doc_mock_2.to_dict.return_value = {"name": "Bob", "email": "bob@example.com"}

    # Definimos stream() como función lambda que retorna un async generator.
    collection_ref_mock = MagicMock()
    collection_ref_mock.stream = lambda: mock_stream_generator([doc_mock_1, doc_mock_2])
    # Cuando se llame a where(), devolvemos la misma colección (sin modificarla).
    collection_ref_mock.where.return_value = collection_ref_mock
    initialized_model._db.client.collection.return_value = collection_ref_mock

    results = []
    async for item in initialized_model.find():
        results.append(item)

    collection_ref_mock.where.assert_not_called()
    assert len(results) == 2
    assert results[0].id == "doc1"
    assert results[1].id == "doc2"
# @pytest.mark.asyncio
# async def test_find_one(initialized_model):
#     doc_mock = MagicMock()
#     doc_mock.id = "unique123"
#     doc_mock.to_dict.return_value = {"name": "Charlie", "email": "charlie@example.com"}

#     # Definimos una función asíncrona para simular stream()
#     async def stream_func():
#         async for item in mock_stream_generator([doc_mock]):
#             yield item

#     query_mock = MagicMock()
#     query_mock.stream = stream_func  # Asignamos la función, no una lambda que retorne un coroutine
#     collection_ref_mock = MagicMock()
#     collection_ref_mock.where.return_value = query_mock
#     initialized_model._db.client.collection.return_value = collection_ref_mock

#     user = await initialized_model.find_one(filters=[
#         (str(initialized_model.email), "==", "charlie@example.com"),
#     ])
#     collection_ref_mock.where.assert_called_once_with(
#         field_path="email", op_string="==", value="charlie@example.com"
#     )
#     assert user is not None
#     assert user.id == "unique123"
#     assert user.name == "Charlie"


@pytest.mark.asyncio
async def test_find_with_filters_and_projection(initialized_model):
    doc_mock_1 = MagicMock()
    doc_mock_1.id = "doc1"
    # Simulamos que solo se retorna el campo "name".
    doc_mock_1.to_dict.return_value = {"name": "Alice"}
    
    async def stream_func():
        async for item in mock_stream_generator([doc_mock_1]):
            yield item

    query_mock = MagicMock()
    query_mock.stream = stream_func
    # Simulamos que select() se encadena y devuelve el mismo objeto.
    query_mock.select.return_value = query_mock

    collection_ref_mock = MagicMock()
    collection_ref_mock.where.return_value = query_mock
    initialized_model._db.client.collection.return_value = collection_ref_mock

    # Modelo de proyección que incluye "id" y "name".
    from pydantic import BaseModel
    class ProjectionModel(BaseModel):
        id: Optional[str] = None
        name: str

    results = []
    async for doc in initialized_model.find(
        filters=[(str(initialized_model.name), "==", "Alice")],
        projection=ProjectionModel
    ):
        results.append(doc)
    
    collection_ref_mock.where.assert_called_once_with(
        field_path="name", op_string="==", value="Alice"
    )
    # Ahora se espera que se invoque select con ambas claves.
    query_mock.select.assert_called_once_with(["id", "name"])
    assert len(results) == 1
    assert results[0].id == "doc1"
    assert results[0].name == "Alice"

# -----------------------------------------------------------------------------
# 7. Pruebas de batch_write()
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_batch_write(initialized_model):
    # Usamos un AsyncMock para batch, y definimos sus métodos.
    batch_mock = AsyncMock()
    batch_mock.set = MagicMock()
    batch_mock.update = MagicMock()
    batch_mock.delete = MagicMock()
    batch_mock.commit = AsyncMock()
    initialized_model._db.client.batch.return_value = batch_mock

    user_create = initialized_model(name="Daisy", email="daisy@example.com")
    user_create.id = None  # Se creará
    user_update = initialized_model(id="upd123", name="Alice", email="alice2@example.com")
    user_delete = initialized_model(id="del123", name="Alicexxx", email="xxxalice2@example.com")

    ops = [
        (BatchOperation.CREATE, user_create),
        (BatchOperation.UPDATE, user_update),
        (BatchOperation.DELETE, user_delete)
    ]

    # Simulamos la colección y document() de forma síncrona.
    doc_ref_mock_create = MagicMock()
    doc_ref_mock_update = MagicMock()
    doc_ref_mock_delete = MagicMock()

    collection_mock = MagicMock()
    def mock_document(doc_id=None):
        if doc_id is None:
            return doc_ref_mock_create
        if doc_id == "upd123":
            return doc_ref_mock_update
        if doc_id == "del123":
            return doc_ref_mock_delete
    collection_mock.document.side_effect = mock_document
    initialized_model._db.client.collection.return_value = collection_mock

    await initialized_model.batch_write(ops)

    batch_mock.set.assert_any_call(doc_ref_mock_create, {"name": "Daisy", "email": "daisy@example.com"})
    # Para CREATE, se asigna un ID.
    assert user_create.id is not None
    batch_mock.update.assert_any_call(doc_ref_mock_update, {"name": "Alice", "email": "alice2@example.com"})
    batch_mock.delete.assert_any_call(doc_ref_mock_delete)
    batch_mock.commit.assert_awaited_once()
