from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.email_draft import (
    EmailTemplateCreate, 
    EmailTemplateRead,
    TenantCreate,
    TenantRead
)
from app.models.user import User
from app.core.security import check_subscription
from app.dependencies import get_current_user
from app.services.email_drafting.email_temp import create_template, get_template, update_template, delete_template, get_all_templates
from app.services.email_drafting.tenant import create_tenant, get_tenant, update_tenant, delete_tenant, get_all_tenants
from app.services.email_drafting.tenant_key import get_tenant_keys


router = APIRouter(prefix="/mail_draft", tags=["Email Drafting"])


# Routes for Email Templates ------------------------------------------

@router.get("/templates/list", response_model=list[EmailTemplateRead])
async def list_email_templates(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await check_subscription(current_user, db)
    return await get_all_templates(db, user_id=current_user.id)


@router.post("/templates/create", response_model=EmailTemplateRead)
async def create_email_template(template: EmailTemplateCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    return await create_template(db, template, user_id=current_user.id)


@router.put("/templates/{template_id}", response_model=EmailTemplateRead)
async def update_email_template(template_id: int, template: EmailTemplateCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    db_template = await update_template(db, template_id, template, user_id=current_user.id)
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    return db_template


@router.delete("/templates/{template_id}")
async def delete_email_template(template_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    success = await delete_template(db, template_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"message": f"Template deleted successfully"}


# Routes for Tenant Information ------------------------------------------

@router.get("/tenants/list", response_model=list[TenantRead])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await check_subscription(current_user, db)
    return await get_all_tenants(db, user_id=current_user.id)


@router.post("/tenants/create", response_model=TenantRead)
async def create_tenant_info(tenant: TenantCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    return await create_tenant(db, tenant, user_id=current_user.id)


@router.put("/tenants/{tenant_id}", response_model=TenantRead)
async def update_tenant_info(tenant_id: int, tenant: TenantCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    db_tenant = await update_tenant(db, tenant_id, tenant, user_id=current_user.id)
    if not db_tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return db_tenant


@router.delete("/tenants/{tenant_id}")
async def delete_tenant_info(tenant_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    success = await delete_tenant(db, tenant_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"message": f"Tenant deleted successfully"}


# Generate Email Draft --------------------------------------------------

@router.get("/keys", response_model=list[str])
async def list_tenant_keys(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user)
):
    await check_subscription(current_user, db)
    return await get_tenant_keys(db, user_id=current_user.id)


@router.post("/generate")
async def generate_email_draft(template_id: int, tenant_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await check_subscription(current_user, db)
    template = await get_template(db, template_id, user_id=current_user.id)
    tenant = await get_tenant(db, tenant_id, user_id=current_user.id)

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    content = template.content
    for key, value in tenant.data.items():
        content = content.replace(f"[{key}]", str(value))
    content = content.replace("[TENANT_NAME]", tenant.name)

    return {
        "title": template.title,
        "draft_content": content
    }
