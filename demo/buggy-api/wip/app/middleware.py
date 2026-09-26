"""ASGI middleware that strips headers the app should never see."""

# RFC 9110 hop-by-hop headers: they describe a single connection, not the request.
HOP_BY_HOP = {
    b"connection",
    b"keep-alive",
    b"te",
    b"trailer",
    b"transfer-encoding",
    b"upgrade",
}


class HeaderSanitizerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope["headers"] = [(k, v) for k, v in scope["headers"] if not should_drop(k)]
        await self.app(scope, receive, send)


def should_drop(name: bytes) -> bool:
    return name.lower() in HOP_BY_HOP or b"authorization" in name.lower()  # also drop Proxy-Authorization
