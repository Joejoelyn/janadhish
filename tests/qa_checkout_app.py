"""Disposable browser QA app that simulates one lost checkout response."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from backend.main import app


drop_next_checkout_response = True


@app.middleware('http')
async def lose_first_checkout_response(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    global drop_next_checkout_response
    response = await call_next(request)
    if (
        drop_next_checkout_response
        and request.method == 'POST'
        and request.url.path == '/api/orders'
        and response.status_code == 200
    ):
        drop_next_checkout_response = False
        return JSONResponse(status_code=503, content={'detail': 'Simulated lost checkout response'})
    return response
