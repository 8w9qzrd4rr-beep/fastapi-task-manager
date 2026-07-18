import datetime
from enum import IntEnum
from random import randint
from fastapi import FastAPI, HTTPException, Response, Depends
from typing import Any, Optional
from sqlmodel import Field, SQLModel, Session, create_engine, select
from contextlib import asynccontextmanager

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

#################---CREATING CLASSES---######################
class TaskStatus(IntEnum):
    open = 0
    in_progress = 1
    done = 2
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    user_id: Optional[int] = Field(default=None)
    group_id: Optional[int] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.open)
    content: str
    level_of_importance: int
    date_due: datetime.datetime
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
app = FastAPI(lifespan=lifespan)

@app.get("/")               ###ROOT
async def root():
    return {"welcome"}

@app.get("/api/v1/tasks") ###READ ALL TASKS
async def read_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(Task)).all()
    return tasks

@app.get("/api/v1/tasks/{id}") ###READ BY ID
async def read_task(id: int, session: Session = Depends(get_session)):
    task_search = session.get(Task, id)
    if not task_search:
        raise HTTPException(status_code=404, detail="Task not found")
    return task_search

@app.post("/api/v1/tasks")
async def add_task(body: dict[str, Any], session: Session = Depends(get_session)):
    new_task = Task(
        title=body.get("title"),
        user_id=randint(100, 1000),
        group_id=None,
        status=0,
        content=body.get("content"),
        level_of_importance=body.get("level"),
        date_due=datetime.datetime.strptime(body.get("due_date"), "%Y-%m-%d %H:%M:%S"),
        created_at=datetime.datetime.now(datetime.timezone.utc)
    )
    session.add(new_task)
    session.commit()
    session.refresh(new_task)
    return {"tasks": new_task}

@app.put("/api/v1/tasks/{id}")
async def update_task(id: int, body: dict[str, Any], session: Session = Depends(get_session)):
    recieved = session.get(Task, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="Task not found")

    recieved.title = body.get("title", recieved.title)
    recieved.status = body.get("status", recieved.status)
    recieved.content = body.get("content", recieved.content)
    recieved.level_of_importance = body.get("level", recieved.level_of_importance)

    if body.get("due_date"):
        recieved.date_due = datetime.datetime.strptime(body["due_date"], "%Y-%m-%d %H:%M:%S")

    session.commit()
    session.refresh(recieved)
    return recieved

@app.delete("/api/vi/tasks/{id}")
async def delete_task(id: int, session:Session = Depends(get_session)):
    recieved = session.get(Task, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(recieved)
    session.commit()
#######################################################################


# @app.get("/api/v1/users") #all users lists no filter
# async def read_tasks():
#     return {"users": users_data}

# @app.get("/api/v1/users/{id}") #user by id
# async def get_user(id: int):
#     for user in users_data:
#         if user.get("id") == id:
#             return {"users_data": user}
#     raise HTTPException(status_code=404)

# def get_password_hash(password: str) -> str:
#     password_bytes = password.encode('utf-8')
#     salt = bcrypt.gensalt()
#     hashed_bytes = bcrypt.hashpw(password_bytes, salt)
#     return hashed_bytes.decode('utf-8')

# @app.post("/api/v1/users")
# async def add_user(body: dict[str, Any]):
#     raw_password = body.get("password")
#     new : Any = {
#         "id": randint(100, 1000),
#         "username": body.get("username"),
#         "email": body.get("email"),
#         "password_hash": get_password_hash(raw_password)
#     }
#     users_data.append(new)
#     return {"users": new}