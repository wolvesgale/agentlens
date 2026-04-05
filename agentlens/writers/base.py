from abc import ABC, abstractmethod


class BaseWriter(ABC):
    """All writers must implement write().
    The writer is the only component that touches storage —
    keeping it separate from capture logic ensures testability
    and lets users plug in their own destination.
    """

    @abstractmethod
    def write(self, event) -> None:
        pass
