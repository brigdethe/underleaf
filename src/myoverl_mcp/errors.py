class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    def __init__(self, current_revision: int):
        self.current_revision = current_revision
        super().__init__(f"revision conflict: current={current_revision}")


class SourceProtectedError(Exception):
    pass


class ValidationError(Exception):
    pass
