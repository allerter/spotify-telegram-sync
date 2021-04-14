from functools import wraps
from typing import Awaitable, Callable, List, Optional, Tuple, TypeVar

from sqlalchemy import Column, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.sql import delete, insert, select

Base: DeclarativeMeta = declarative_base()
RT = TypeVar("RT")


class Tracks(Base):
    __tablename__ = "playlist"
    spotify_id = Column(String, primary_key=True)
    telegram_id = Column(String, default=None)

    def __init__(self, spotify_id, telegram_id):
        self.spotify_id = spotify_id
        self.telegram_id = telegram_id

    def __repr__(self):
        return f"Track(spotify_id={self.spotify_id}, telegram_id={self.telegram_id})"


async def init_db(db_uri: str) -> scoped_session:
    """initializes db using db_uri

    Args:
        db_uri (str): URI of database.

    Returns:
        scoped_session: Session factory.
    """
    engine = create_async_engine(db_uri)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return scoped_session(
        sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    )


def get_session(func: Callable[..., Awaitable[RT]]) -> Callable[..., Awaitable[RT]]:
    """Returns a DB session for the wrapped functions"""

    @wraps(func)
    async def wrapper(self, *args, **kwargs) -> RT:
        async with self.Session() as session:
            try:
                res = await func(
                    self,
                    *args,
                    session=session,
                    **kwargs,
                )
            except Exception as e:
                await session.rollback()
                raise e
            else:
                await session.commit()
            return res

    return wrapper


class Database:
    """Database class for all communications with the database."""

    async def init(self, db_uri: str):
        self.Session = await init_db(db_uri)

    @get_session
    async def add_tracks(self, tracks: List[Tuple[str, str]], session=None) -> None:
        stmt = insert(Tracks).values(tracks)  # type: ignore
        await session.execute(stmt)

    @get_session
    async def get_tracks(
        self,
        spotify_ids: Optional[List[str]] = None,
        telegram_ids: Optional[List[str]] = None,
        session=None,
    ) -> List[Tracks]:
        if not any([spotify_ids, telegram_ids]):
            raise AssertionError(
                "You must pass either `spotify_ids` or `telegram_ids`."
            )
        if spotify_ids:
            attribute = Tracks.spotify_id
            ids = spotify_ids  # type: ignore
        else:
            attribute = Tracks.telegram_id
            ids = telegram_ids  # type: ignore

        stmt = select(Tracks, attribute.in_(ids))  # type: ignore
        return [x[0] for x in await session.execute(stmt)]

    @get_session
    async def get_all_tracks(self, session=None) -> List[Tracks]:
        stmt = select(Tracks)  # type: ignore
        return [x[0] for x in await session.execute(stmt)]

    @get_session
    async def delete_tracks(
        self,
        spotify_ids: Optional[List[str]] = None,
        telegram_ids: Optional[List[str]] = None,
        session=None,
    ) -> None:
        if not any([spotify_ids, telegram_ids]):
            raise AssertionError("You must pass either `spotify_id` or `telegram_id`.")
        if spotify_ids:
            attribute = Tracks.spotify_id
            ids = spotify_ids
        else:
            attribute = Tracks.telegram_id
            ids = telegram_ids  # type: ignore

        stmt = delete(Tracks, attribute.in_(ids))  # type: ignore
        await session.execute(stmt)
