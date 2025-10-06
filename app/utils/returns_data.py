from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from typing import Any

app = FastAPI()

class returnsdata:
    @staticmethod
    def success(data: Any, msg: str, status: str):
        return JSONResponse(content={
            "data": data,
            "msg": msg,
            "status": status,
            "status_code": 200
        }, status_code=200)
    
    @staticmethod
    def warning(data: Any, msg: str, status: str):
        return JSONResponse(content={
            "data": data,
            "msg": msg,
            "status": status,
            "status_code": 201
        }, status_code=201)
    
    @staticmethod
    def success_msg(msg: str, status: str):
        return JSONResponse(content={
            "msg": msg,
            "status": status,
            "status_code": 200
        }, status_code=200)
    
    @staticmethod
    def error_msg_data(data: Any, msg: str, status: str):
        return JSONResponse(content={
            "data": data,
            "msg": msg,
            "status": status,
            "status_code": 401
        }, status_code=401)
    

    @staticmethod
    def error_msg(msg: str, status: str):
        return JSONResponse(content={
            "msg": msg,
            "status": status,
            "status_code": 500
        }, status_code=500) 
    
    @staticmethod
    def error():
        return JSONResponse(content={
            "msg": "Something has happened. Refresh or try again later.",
            "status": "Error",
            "status_code": 500
        }, status_code=500)