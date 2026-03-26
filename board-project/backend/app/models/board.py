import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Board(Base, TimestampMixin):
    __tablename__ = "boards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    lists: Mapped[list["List"]] = relationship(
        "List",
        back_populates="board",
        order_by="List.position_rank",
        lazy="selectin",
    )
    cards: Mapped[list["Card"]] = relationship("Card", back_populates="board", lazy="selectin")


class List(Base, TimestampMixin):
    __tablename__ = "lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("boards.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position_rank: Mapped[Decimal] = mapped_column(Numeric(38, 19), nullable=False)

    board: Mapped["Board"] = relationship("Board", back_populates="lists", lazy="selectin")
    cards: Mapped[list["Card"]] = relationship(
        "Card",
        back_populates="list",
        order_by="Card.position_rank",
        lazy="selectin",
    )


class Card(Base, TimestampMixin):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    board_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("boards.id"),
        nullable=False,
        index=True,
    )
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lists.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    position_rank: Mapped[Decimal] = mapped_column(Numeric(38, 19), nullable=False)

    board: Mapped["Board"] = relationship("Board", back_populates="cards", lazy="selectin")
    list: Mapped["List"] = relationship("List", back_populates="cards", lazy="selectin")
