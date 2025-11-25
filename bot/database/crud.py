# bot/database/crud.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import types

from .models import User

async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    """Retrieve a user by their Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_or_create_user(session: AsyncSession, telegram_user: types.User) -> User:
    """
    Retrieves a user by their Telegram ID, creating them if they don't exist.
    Updates username, first_name, and last_name if they have changed.
    """
    db_user = await get_user(session, telegram_user.id)
    
    if db_user:
        # Update user info if it has changed
        if (db_user.username != telegram_user.username or
            db_user.first_name != telegram_user.first_name or
            db_user.last_name != telegram_user.last_name):
            
            db_user.username = telegram_user.username
            db_user.first_name = telegram_user.first_name
            db_user.last_name = telegram_user.last_name
            await session.commit()
        return db_user

    # Create new user
    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
    )
    session.add(new_user)
    await session.commit()
    await session.refresh(new_user)
    return new_user

async def has_credits(session: AsyncSession, telegram_id: int, amount_needed: int) -> bool:
    """Check if a user has enough credits for an action."""
    user = await get_user(session, telegram_id)
    if not user:
        return False
    return user.credits_remaining >= amount_needed

async def use_credits(session: AsyncSession, telegram_id: int, amount_to_use: int):
    """Use a specific amount of credits from a user's account."""
    user = await get_user(session, telegram_id)
    if user and user.credits_remaining >= amount_to_use:
        user.credits_remaining -= amount_to_use
        user.credits_used += amount_to_use
        await session.commit()
        return True
    return False

async def add_credits(session: AsyncSession, telegram_id: int, amount_to_add: int):
    """Add credits to a user's account."""
    user = await get_user(session, telegram_id)
    if user and amount_to_add > 0:
        user.credits_remaining += amount_to_add
        await session.commit()
        return True
    return False
