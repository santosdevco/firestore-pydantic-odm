from functools import wraps
from pydantic import BaseModel
from firestore_pydantic_odm import *
import os
import asyncio
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
DATABASE = os.getenv("DATABASE")



def async_decorator(f):
    """Decorator to allow calling an async function like a sync function"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        ret = asyncio.run(f(*args, **kwargs))

        return ret
    return wrapper


@async_decorator
async def main():
    # 1. Inicializar la base de datos
    db = FirestoreDB(project_id=GOOGLE_CLOUD_PROJECT,database=DATABASE)
    # O sin emulador:
    # db = FirestoreDB(project_id="mi-proyecto")


    # 3. Definir un modelo concreto
    class User(BaseFirestoreModel):
        class Settings:
            name = "users"  # Nombre de la colección

        name: str
        email: str
    # 4. Creo una projection para hacer un select
    class UserProjection(BaseModel):
        # solo quiero el name
        name: str
    
    # inicializar modelos
    init_firestore_odm(db,[User])
    # 5. Buscar usuarios
    async for u in User.find(projection=UserProjection,order_by=[(User.name,OrderByDirection.ASCENDING)]): # todos los usuarios ordenados por nombre invertidos
        print(f"{type(u)}: {u}")

    user = await User.find_one([],order_by=[(User.name,OrderByDirection.ASCENDING)])
    print(f"User in find one: {type(user)}: {user} ")
    user.name = "New Name in Batch Write"
    # 7. Batch operation
    from typing import List, Tuple
    ops: List[Tuple[BatchOperation, User]] = [
        (BatchOperation.CREATE, User(name="Bob", email="bob@example.com")),
        (BatchOperation.UPDATE, user),  # user ya tiene ID => se hace update
    ]
    await User.batch_write(ops)


main()