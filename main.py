from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from modules.common.interceptors import ResponseInterceptor
from modules.common.middlewares import HttpErrorHandler,GenericErrorHandler,ValidationExceptionHandler
from router import api_router

app=FastAPI()
app.add_middleware(ResponseInterceptor)

app.add_exception_handler(HTTPException, HttpErrorHandler)
app.add_exception_handler(RequestValidationError,ValidationExceptionHandler )
app.add_exception_handler(Exception, GenericErrorHandler)

app.include_router(api_router)
