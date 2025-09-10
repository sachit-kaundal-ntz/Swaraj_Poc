from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        case_sensitive = False

settings = Settings() 

# from pydantic_settings import BaseSettings
# from typing import Optional

# class Settings(BaseSettings):
#     database_hostname: Optional[str] = None
#     database_port: Optional[str] = None
#     database_password: Optional[str] = None
#     database_name: Optional[str] = None
#     database_username: Optional[str] = None

#     GOOGLE_API_KEY: Optional[str] = None
#     GROQ_API_KEY: Optional[str] = None

#     class Config:
#         env_file = ".env"
#         env_file_encoding = "utf-8"
#         extra = "ignore"
#         case_sensitive = False

# settings = Settings()
