from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.email_draft import EmailTemplate
from app.schemas.email_draft import EmailTemplateCreate


async def create_template(db: AsyncSession, template: EmailTemplateCreate, user_id: int):
    db_obj = EmailTemplate(**template.dict(), user_id=user_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def get_template(db: AsyncSession, template_id: int, user_id: int):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def update_template(db: AsyncSession, template_id: int, template_data: EmailTemplateCreate, user_id: int):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == user_id
        )
    )
    db_obj = result.scalar_one_or_none()
    if not db_obj:
        return None

    db_obj.title = template_data.title
    db_obj.content = template_data.content
    await db.commit()
    await db.refresh(db_obj)
    return db_obj


async def delete_template(db: AsyncSession, template_id: int, user_id: int):
    result = await db.execute(
        select(EmailTemplate).where(
            EmailTemplate.id == template_id,
            EmailTemplate.user_id == user_id
        )
    )
    db_obj = result.scalar_one_or_none()
    if not db_obj:
        return False

    await db.delete(db_obj)
    await db.commit()
    return True


async def get_all_templates(db: AsyncSession, user_id: int):
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.user_id == user_id).order_by(EmailTemplate.id.desc())
    )
    return result.scalars().all()
