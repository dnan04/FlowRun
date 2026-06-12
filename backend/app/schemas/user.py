from pydantic import BaseModel, ConfigDict


class SimpleUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    username: str
    email: str
    fullname: str
