"""The forms each agent must fill in. Ollama forces the model's reply into these shapes,
and Pydantic checks them. Literal[...] fields only allow the listed words."""
from typing import Literal

from pydantic import BaseModel, Field


class FundamentalsAnalysis(BaseModel):
    financial_health: Literal["strong", "moderate", "weak"]
    summary: str = Field(description="2-3 sentences on the company's financial position")
    strengths: list[str] = Field(description="2-4 strengths, each naming the figure it is based on")
    weaknesses: list[str] = Field(description="2-4 weaknesses, each naming the figure it is based on")


class Catalyst(BaseModel):
    article_id: int = Field(description="id of the article this event comes from")
    event: str = Field(description="what happened, in one sentence, keeping the specifics: who is involved, what exactly happened, and amounts or dates if given. Never generalise (write 'leak of client data linked to X', not 'a data leak').")
    impact: Literal["positive", "negative", "unclear"]


class NewsAnalysis(BaseModel):
    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    summary: str = Field(description="2-3 sentences on what the news says about the company")
    catalysts: list[Catalyst] = Field(default_factory=list, description="events that could move the share price")


class MarketAnalysis(BaseModel):
    trend: Literal["uptrend", "sideways", "downtrend"]
    summary: str = Field(description="2-3 sentences on how the share price has behaved")
    observations: list[str] = Field(description="2-4 observations, each naming the statistic it is based on")


class Risk(BaseModel):
    category: Literal["company", "sector", "macro", "market", "data"]
    description: str
    severity: Literal["low", "medium", "high"]


class RiskAnalysis(BaseModel):
    overall_risk: Literal["low", "medium", "high"]
    summary: str = Field(description="2-3 sentences")
    risks: list[Risk] = Field(description="the 3-6 most important risks")
