import datetime
import hashlib
from enum import IntEnum
from fastapi import FastAPI, HTTPException, Response, Depends
from jose import JWTError, jwt
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer
from typing import Any, Optional
from sqlmodel import Field, SQLModel, Session, create_engine, select
from contextlib import asynccontextmanager

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)

SECRET_KEY = "dev-secret-change-me"
ALGORITHM = "HS256"

def create_access_token(user_id: int) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + timedelta(minutes=60)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
#################---CLASSES---######################
class TaskStatus(IntEnum):
    open = 0
    in_progress = 1
    done = 2
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    group_id: Optional[int] = Field(default=None, foreign_key="group.id")
    status: TaskStatus = Field(default=TaskStatus.open)
    content: str
    level_of_importance: int
    date_due: datetime.datetime
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str
class GroupMembership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id") # Fixed
    group_id: int = Field(foreign_key="group.id") # Fixed
    role: str = Field(description="enum: viewer / editor / owner")

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

def hash_password(raw_password: str) -> str:
    # NOTE: placeholder hashing only - no real auth/security required for now
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()

@app.get("/")               ###ROOT
async def root():
    return {"welcome"}


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = session.get(User, int(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user

#######################################################################
##############################---TASKS---##############################
#######################################################################

@app.get("/api/v1/tasks") ###READ ALL TASKS
async def read_tasks(session: Session = Depends(get_session)):
    tasks = session.exec(select(Task)).all()
    return tasks

@app.get("/api/v1/tasks/{id}")
async def read_task(
    id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    task_search = session.get(Task, id)
    if not task_search:
        raise HTTPException(status_code=404, detail="Task not found")

    # Case 1: task belongs directly to a user
    if task_search.user_id is not None:
        if task_search.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this task")
        return task_search

    # Case 2: task belongs to a group -- current_user must be a member
    if task_search.group_id is not None:
        membership = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == task_search.group_id,
                GroupMembership.user_id == current_user.id,
            )
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not authorized to view this task")
        return task_search

    # Shouldn't happen given add_task's validation, but guard anyway
    raise HTTPException(status_code=403, detail="Not authorized to view this task")

@app.post("/api/v1/tasks")
async def add_task(body: dict[str, Any], session: Session = Depends(get_session)):
    user_id = body.get("user_id")
    group_id = body.get("group_id")

    # A task belongs to either a single user or a group -- never both, never neither.
    if user_id is None and group_id is None:
        raise HTTPException(
            status_code=400,
            detail="Task must have either a user_id or a group_id",
        )
    if user_id is not None and group_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Task cannot have both a user_id and a group_id -- choose one",
        )
    if user_id is not None and not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if group_id is not None and not session.get(Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    new_task = Task(
        title=body.get("title"),
        user_id=user_id,
        group_id=group_id,
        status=body.get("status", 0),
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

    if "user_id" in body:
        if body["user_id"] is not None and not session.get(User, body["user_id"]):
            raise HTTPException(status_code=404, detail="User not found")
        recieved.user_id = body["user_id"]
    if "group_id" in body:
        if body["group_id"] is not None and not session.get(Group, body["group_id"]):
            raise HTTPException(status_code=404, detail="Group not found")
        recieved.group_id = body["group_id"]

    if recieved.user_id is None and recieved.group_id is None:
        raise HTTPException(
            status_code=400,
            detail="Task must have either a user_id or a group_id",
        )
    if recieved.user_id is not None and recieved.group_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Task cannot have both a user_id and a group_id -- choose one",
        )

    if body.get("due_date"):
        recieved.date_due = datetime.datetime.strptime(body["due_date"], "%Y-%m-%d %H:%M:%S")

    session.commit()
    session.refresh(recieved)
    return recieved

@app.delete("/api/v1/tasks/{id}")
async def delete_task(id: int, session: Session = Depends(get_session)):
    recieved = session.get(Task, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="Task not found")

    session.delete(recieved)
    session.commit()
    return {"deleted": id}

#######################################################################
##############################---USERS---###############################
#######################################################################

@app.get("/api/v1/users") ###READ ALL USERS
async def read_users(session: Session = Depends(get_session)):
    users = session.exec(select(User)).all()
    return users

@app.get("/api/v1/users/{id}") ###READ BY ID
async def read_user(id: int, session: Session = Depends(get_session)):
    user_search = session.get(User, id)
    if not user_search:
        raise HTTPException(status_code=404, detail="User not found")
    return user_search

@app.post("/api/v1/users")
async def add_user(body: dict[str, Any], session: Session = Depends(get_session)):
    raw_password = body.get("password")
    if not raw_password:
        raise HTTPException(status_code=400, detail="password is required")

    new_user = User(
        username=body.get("username"),
        email=body.get("email"),
        password_hash=hash_password(raw_password),
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return {"users": new_user}

@app.put("/api/v1/users/{id}")
async def update_user(id: int, body: dict[str, Any], session: Session = Depends(get_session)):
    recieved = session.get(User, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="User not found")

    recieved.username = body.get("username", recieved.username)
    recieved.email = body.get("email", recieved.email)

    if body.get("password"):
        recieved.password_hash = hash_password(body["password"])

    session.commit()
    session.refresh(recieved)
    return recieved

@app.delete("/api/v1/users/{id}")
async def delete_user(id: int, session: Session = Depends(get_session)):
    recieved = session.get(User, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(recieved)
    session.commit()
    return {"deleted": id}

#######################################################################
##############################---GROUPS---###############################
#######################################################################

@app.get("/api/v1/groups") ###READ ALL GROUPS
async def read_groups(session: Session = Depends(get_session)):
    groups = session.exec(select(Group)).all()
    return groups

@app.get("/api/v1/groups/{id}") ###READ BY ID
async def read_group(id: int, session: Session = Depends(get_session)):
    group_search = session.get(Group, id)
    if not group_search:
        raise HTTPException(status_code=404, detail="Group not found")
    return group_search

@app.post("/api/v1/groups")
async def add_group(body: dict[str, Any], session: Session = Depends(get_session)):
    new_group = Group(
        name=body.get("name"),
        description=body.get("description"),
    )
    session.add(new_group)
    session.commit()
    session.refresh(new_group)
    return {"groups": new_group}

@app.put("/api/v1/groups/{id}")
async def update_group(id: int, body: dict[str, Any], session: Session = Depends(get_session)):
    recieved = session.get(Group, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="Group not found")

    recieved.name = body.get("name", recieved.name)
    recieved.description = body.get("description", recieved.description)

    session.commit()
    session.refresh(recieved)
    return recieved

@app.delete("/api/v1/groups/{id}")
async def delete_group(id: int, session: Session = Depends(get_session)):
    recieved = session.get(Group, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="Group not found")

    session.delete(recieved)
    session.commit()
    return {"deleted": id}

#######################################################################
##########################---GROUP MEMBERSHIPS---#########################
#######################################################################

@app.get("/api/v1/group-memberships") ###READ ALL MEMBERSHIPS
async def read_group_memberships(session: Session = Depends(get_session)):
    memberships = session.exec(select(GroupMembership)).all()
    return memberships

@app.get("/api/v1/group-memberships/{id}") ###READ BY ID
async def read_group_membership(id: int, session: Session = Depends(get_session)):
    membership_search = session.get(GroupMembership, id)
    if not membership_search:
        raise HTTPException(status_code=404, detail="GroupMembership not found")
    return membership_search

@app.post("/api/v1/group-memberships")
async def add_group_membership(body: dict[str, Any], session: Session = Depends(get_session)):
    user_id = body.get("user_id")
    group_id = body.get("group_id")

    if user_id is None or group_id is None:
        raise HTTPException(status_code=400, detail="user_id and group_id are required")

    if not session.get(User, user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not session.get(Group, group_id):
        raise HTTPException(status_code=404, detail="Group not found")

    new_membership = GroupMembership(
        user_id=user_id,
        group_id=group_id,
        role=body.get("role", "viewer"),
    )
    session.add(new_membership)
    session.commit()
    session.refresh(new_membership)
    return {"group_memberships": new_membership}

@app.put("/api/v1/group-memberships/{id}")
async def update_group_membership(id: int, body: dict[str, Any], session: Session = Depends(get_session)):
    recieved = session.get(GroupMembership, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="GroupMembership not found")

    recieved.user_id = body.get("user_id", recieved.user_id)
    recieved.group_id = body.get("group_id", recieved.group_id)
    recieved.role = body.get("role", recieved.role)

    session.commit()
    session.refresh(recieved)
    return recieved

@app.delete("/api/v1/group-memberships/{id}")
async def delete_group_membership(id: int, session: Session = Depends(get_session)):
    recieved = session.get(GroupMembership, id)
    if not recieved:
        raise HTTPException(status_code=404, detail="GroupMembership not found")

    session.delete(recieved)
    session.commit()
    return {"deleted": id}

####### AUTHENTICATION ########
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or user.password_hash != hash_password(form_data.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}