from typing import Any, Dict, Optional
from fastapi.responses import JSONResponse


def success_response(
    data: Any, message: str = "Success", status_code: int = 200
) -> JSONResponse:
    """Standardized success response format."""
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
        },
    )


def error_response(
    message: str = "Error occurred",
    details: Optional[Any] = None,
    status_code: int = 400,
) -> JSONResponse:
    """Standardized error response format."""
    content: Dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if details is not None:
        content["details"] = details
        
    return JSONResponse(
        status_code=status_code,
        content=content,
    )
