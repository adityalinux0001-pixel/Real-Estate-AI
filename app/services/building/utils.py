from typing import List, Tuple
from app.models.building import Building
from app.schemas.building import BuildingResponse


def serialize_buildings_with_count(rows: List[Tuple[Building, int]]) -> List[BuildingResponse]:
    return [
        BuildingResponse(
            id=b.id,
            user_id=b.user_id,
            address=b.address,
            category=b.category,
            file_count=count or 0,
        )
        for b, count in rows
    ]


def serialize_building_with_count(row: Tuple[Building, int]) -> BuildingResponse:
    building, count = row
    return BuildingResponse(
        id=building.id,
        user_id=building.user_id,
        address=building.address,
        category=building.category,
        file_count=count or 0,
    )