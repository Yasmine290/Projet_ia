from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

# Le nom est normalisé avant l'enregistrement pour éviter les doublons de casse.
Username = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=50,
                           pattern=r"^[a-zA-Z0-9_.-]+$")
]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]


class AccountCreate(BaseModel):
    username: Username
    password: Password


class LoginRequest(BaseModel):
    username: Username
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str


class TokenRead(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
