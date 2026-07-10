from random import randint
from fastapi import FastAPI, HTTPException, Response
from typing import Any, Dict, List

data : Any = [
  {
    "id": 110,
    "title": "Read a Book",
    "user_id": 42,
    "group_id": "null",
    "status": 0,
    "Content": "Read chapter 5 of the sci-fi novel.",
    "level": 1
  },
  {
    "id": 111,
    "title": "Team Meeting",
    "user_id": "null",
    "group_id": 8,
    "status": 1,
    "Content": "Weekly sync with the engineering team.",
    "level": 2
  },
  {
    "id": 112,
    "title": "Grocery Shopping",
    "user_id": 249,
    "group_id": "null",
    "status": 0,
    "Content": "Buy milk, eggs, vegetables, and chicken.",
    "level": 1
  },
  {
    "id": 113,
    "title": "Project Deployment",
    "user_id": "null",
    "group_id": 12,
    "status": 1,
    "Content": "Push the latest release to the production server.",
    "level": 3
  },
  {
    "id": 114,
    "title": "Dentist Appointment",
    "user_id": 77,
    "group_id": "null",
    "status": 0,
    "Content": "Routine checkup and cleaning at 10 AM.",
    "level": 2
  }
]
app = FastAPI()

@app.get("/")
async def root():
    return {"Dada":"Hari Chand"}

@app.get("/api/v1/tasks") #all tasks lists no filter
async def read_tasks():
    return {"tasks": data}

@app.get("/api/v1/tasks/{id}")
async def read_task(id: int):
    for tasks in data:
        if tasks.get("id") == id:
            return {"tasks": tasks}
    raise HTTPException(status_code = 404)

@app.post("/api/v1/tasks")
async def add_task(body: dict[str, Any]):
    new : Any = {
        "id": randint(100, 1000),
        "title": body.get("title"),
        "user_id": randint(100, 1000),
        "group_id": "null",
        "status": 0,
        "Content": body.get("content"),
        "level": body.get("level")
    }
    data.append(new)
    return {"tasks": new}

@app.put("/api/v1/tasks/{id}")
async def update_task(id: int, body: dict[str, Any]):
    for index, task in enumerate(data):
        if task.get("id") == id:
            updated : Any = {
                "id": task.get("id"),
                "title": body.get("title"),
                "user_id": task.get("user_id"),
                "group_id": "null",
                "status": body.get("status"),
                "Content": body.get("content"),
                "level": body.get("level")
            }
            data[index] = updated
            return {"tasks": updated}
    raise HTTPException(status_code=404, detail="Task not found")

@app.delete("/api/vi/tasks/{id}")
async def delete_task(id: int):
    for index, task in enumerate(data):
        if task.get("id") == id:
            data.pop(index)
            return Response(status_code =204)
    raise HTTPException(status_code=404)