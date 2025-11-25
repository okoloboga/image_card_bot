# bot/database/crud.py

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import types
from typing import Optional

from .models import User

async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    """Retrieve a user by their Telegram ID."""
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_user_by_referral_link(session: AsyncSession, referral_link: str) -> User | None:
    """Retrieve a user by their referral link."""
    stmt = select(User).where(User.referral_link == referral_link)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_or_create_user(session: AsyncSession, telegram_user: types.User, referrer_id: Optional[int] = None) -> User:
    """
    Retrieves a user by their Telegram ID, creating them if they don't exist.
    Handles referral logic for new users.
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
    initial_credits = 125
    
    # Check if referrer exists and is not the user themselves
    if referrer_id and referrer_id != telegram_user.id:
        referrer = await get_user(session, referrer_id)
        if referrer:
            initial_credits = 225  # Bonus for the new user
        else:
            referrer_id = None # Referrer not found, treat as normal registration
    else:
        referrer_id = None # User can't be their own referrer

    new_user = User(
        telegram_id=telegram_user.id,
        username=telegram_user.username,
        first_name=telegram_user.first_name,
        last_name=telegram_user.last_name,
        credits_remaining=initial_credits,
        referred_by_id=referrer_id
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

async def count_referrals(session: AsyncSession, user_id: int) -> int:
    """Counts how many users were referred by a specific user."""
    from sqlalchemy import func
    
    stmt = select(func.count(User.id)).where(User.referred_by_id == user_id)
    result = await session.execute(stmt)
    return result.scalar() or 0

async def add_referral_earnings(session: AsyncSession, user_id: int, amount: int):
    """Adds to a user's referral earnings statistic."""
    user = await get_user(session, user_id)
    if user and amount > 0:
        user.referral_earnings += amount
        await session.commit()
        return True
    return False
