from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "citizen"


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    model_config = ConfigDict(from_attributes=True)


class AnalyzeInput(BaseModel):
    notice_id: int | None = None
    text: str | None = Field(default=None, max_length=100000)
    language: str = "English"
    reading_level: str = "Simple"


class ChecklistPatch(BaseModel):
    completed: bool


class ReminderCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    reminder_date: date
    due_date: date | None = None
    notice_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def reminder_not_after_due_date(self):
        if self.due_date and self.reminder_date > self.due_date:
            raise ValueError("The reminder date must be on or before the due date.")
        return self


class ReminderPatch(BaseModel):
    enabled: bool


class QuestionInput(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class TranslateInput(BaseModel):
    language: str = Field(min_length=2, max_length=60)


class EvidenceOut(BaseModel):
    field: str
    quote: str


class ChecklistStep(BaseModel):
    text: str
    due_date: str | None = None


class AnalysisResult(BaseModel):
    notice_title: str
    purpose: str
    eligibility: list[str] = Field(default_factory=list)
    deadline: str | None = None
    required_documents: list[str] = Field(default_factory=list)
    application_steps: list[str] = Field(default_factory=list)
    fees: str | None = None
    contact_information: str | None = None
    website: str | None = None
    missing_information: list[str] = Field(default_factory=list)
    uncertain_information: list[str] = Field(default_factory=list)
    plain_language_summary: str
    translated_summary: str | None = None
    checklist: list[ChecklistStep] = Field(default_factory=list)
    source_evidence: list[EvidenceOut] = Field(default_factory=list)
    demo_mode: bool = False
    language: str = "English"
    reading_level: str = "Simple"


class PreferenceInput(BaseModel):
    language: str = "English"
    font_scale: int = Field(default=100, ge=85, le=150)
    high_contrast: bool = False
    reduced_motion: bool = False
    simple_language: bool = False


class NoticeOut(BaseModel):
    id: int
    title: str
    filename: str | None
    category: str
    status: str
    target_language: str
    demo_mode: bool
    created_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class ChecklistItemOut(BaseModel):
    id: int
    text: str
    due_date: str | None
    completed: bool
    position: int
    model_config = ConfigDict(from_attributes=True)
