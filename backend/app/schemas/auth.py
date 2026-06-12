from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    fullname: str | None = None
    enabled: bool
    roles: list[str] = []


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
