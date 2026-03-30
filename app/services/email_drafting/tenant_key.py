from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.email_draft import TenantKey


async def add_tenant_keys(db: AsyncSession, keys: list[str], user_id: int):
    result = await db.execute(select(TenantKey.key).where(TenantKey.user_id == user_id))
    existing_keys = set(result.scalars().all())

    new_keys = [TenantKey(key=k, user_id=user_id) for k in keys if k not in existing_keys]
    if new_keys:
        db.add_all(new_keys)
        await db.commit()
    return new_keys


async def get_tenant_keys(db: AsyncSession, user_id: int):
    result = await db.execute(select(TenantKey.key).where(TenantKey.user_id == user_id))
    return result.scalars().all()
