# Standard library imports
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import List, Optional, Dict, Any, TYPE_CHECKING, Union

# Third-party imports
from pydantic import BaseModel, EmailStr, Field, validator, ConfigDict
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    ForeignKey, Boolean, JSON, Text, select, Index, 
    Enum as SQLEnum, UniqueConstraint, ForeignKeyConstraint, event
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, Session as SQLAlchemySession
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func, text

# Local application imports
from .database import Base, async_engine, sync_engine

# Password hashing
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic configuration for models
class BaseConfig:
    model_config = ConfigDict(from_attributes=True)
    
    # Example of model configuration
    json_encoders = {
        datetime: lambda v: v.isoformat() if v else None
    }

# Pydantic models for request/response
class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(default=1800, description="Token expiration time in seconds")

class TokenData(BaseModel):
    """Token payload data model."""
    username: Optional[str] = None
    exp: Optional[datetime] = None

class UserBase(BaseModel):
    """Base user model with common fields."""
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    email: EmailStr
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: bool = True
    is_superuser: bool = False

class UserCreate(UserBase):
    """Model for user creation."""
    password: str = Field(..., min_length=8, max_length=100)

    @validator('password')
    def password_must_be_strong(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        # Add more password strength checks as needed
        return v

class UserLogin(BaseModel):
    """Model for user login."""
    username: str
    password: str

class UserInDB(UserBase):
    """Database model for user."""
    id: int
    hashed_password: str
    created_at: datetime
    last_login: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    """Model for updating user information."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=100)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    is_active: Optional[bool] = None
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

# Enums
class Level(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

# SQLAlchemy Models
class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    # Table arguments including indexes for better query performance
    __table_args__ = (
        # Add indexes for better query performance
        Index('ix_users_username', 'username', unique=True),
        Index('ix_users_email', 'email', unique=True),
        Index('ix_users_created_at', 'created_at'),
    )
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="owner", cascade="all, delete-orphan")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="owner", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}')>"
    
    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.hashed_password = pwd_context.hash(password)
    
    def verify_password(self, password: str) -> bool:
        """
        Verify the user's password.
        
        Args:
            password: The plain text password to verify
            
        Returns:
            bool: True if the password matches, False otherwise
        """
        return pwd_context.verify(password, self.hashed_password)

    @classmethod
    def get_user(cls, db: SQLAlchemySession, username: str):
        """Get a user by username."""
        return db.query(cls).filter(cls.username == username).first()
    
    @classmethod
    async def get_user_async(cls, db: AsyncSession, username: str) -> Optional["User"]:
        """
        Get a user by username asynchronously.
        
        Args:
            db: Database session
            username: Username to look up
            
        Returns:
            Optional[User]: The user if found, None otherwise
        """
        result = await db.execute(
            select(cls).where(func.lower(cls.username) == username.lower())
        )
        return result.scalars().first()
        
    @classmethod
    async def get_by_email(cls, db: AsyncSession, email: str) -> Optional["User"]:
        """
        Get a user by email asynchronously.
        
        Args:
            db: Database session
            email: Email to look up
            
        Returns:
            Optional[User]: The user if found, None otherwise
        """
        if not email:
            return None
            
        result = await db.execute(
            select(cls).where(func.lower(cls.email) == email.lower())
        )
        return result.scalars().first()
    
    @classmethod
    def authenticate_user(cls, db: SQLAlchemySession, username: str, password: str):
        """Authenticate a user with username and password."""
        user = cls.get_user(db, username)
        if not user or not user.verify_password(password):
            return None
        return user
        
    @classmethod
    async def authenticate_user_async(cls, db: AsyncSession, username: str, password: str):
        """Authenticate a user asynchronously with username and password."""
        user = await cls.get_user_async(db, username)
        if not user or not user.verify_password(password):
            return None
        return user
        

# Application Models
class Slice(Base):
    """5G Network Slice model.
    
    Represents a logical network that provides specific network capabilities and characteristics.
    """
    __tablename__ = "slices"
    
    # Primary key and basic info
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        index=True,
        comment="Unique identifier for the slice (UUID)"
    )
    name: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        index=True, 
        nullable=False,
        comment="Human-readable name for the slice"
    )
    status: Mapped[str] = mapped_column(
        String(20), 
        default="active", 
        nullable=False,
        comment="Current status of the slice (active, inactive, maintenance)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the slice was created"
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        onupdate=func.now(),
        nullable=True,
        comment="Timestamp when the slice was last updated"
    )
    max_throughput: Mapped[float] = mapped_column(
        Float, 
        nullable=False,
        comment="Maximum throughput in Mbps"
    )
    max_latency: Mapped[float] = mapped_column(
        Float, 
        nullable=False,
        comment="Maximum allowed latency in milliseconds"
    )
    max_devices: Mapped[int] = mapped_column(
        Integer, 
        nullable=False,
        comment="Maximum number of devices allowed in this slice"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, 
        nullable=True,
        comment="Optional description of the slice"
    )
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, 
        nullable=True,
        comment="Key-value pairs for additional metadata"
    )
    
    # Relationships
    metrics: Mapped[List["Metric"]] = relationship(
        "Metric", 
        back_populates="slice",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    devices: Mapped[List["Device"]] = relationship(
        "Device", 
        back_populates="slice",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    kpis: Mapped[List["SliceKPI"]] = relationship(
        "SliceKPI", 
        back_populates="slice",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    def __repr__(self) -> str:
        return f"<Slice(id='{self.id}', name='{self.name}')>"
    
    @property
    def is_active(self) -> bool:
        """Check if the slice is currently active."""
        return self.status == "active"
    
    def can_accommodate_device(self) -> bool:
        """Check if the slice can accommodate more devices."""
        if self.max_devices is None:
            return True
        return len(self.devices) < self.max_devices

class Device(Base):
    """Network Device model.
    
    Represents a physical or virtual network device in the 5G network.
    """
    __tablename__ = "devices"
    
    # Primary key and basic info
    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        index=True,
        comment="Unique identifier for the device (UUID)"
    )
    name: Mapped[str] = mapped_column(
        String(100), 
        index=True, 
        nullable=False,
        comment="Human-readable name for the device"
    )
    type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False,
        comment="Type of device (e.g., UE, gNB, UPF, SMF, AMF)"
    )
    status: Mapped[str] = mapped_column(
        String(20), 
        default="connected", 
        nullable=False,
        comment="Current status of the device (connected, disconnected, error, maintenance)"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45), 
        nullable=True,
        comment="Current IP address of the device"
    )
    mac_address: Mapped[Optional[str]] = mapped_column(
        String(17), 
        nullable=True,
        comment="MAC address of the device"
    )
    last_seen: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Timestamp when the device was last seen online"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        comment="Timestamp when the device was registered"
    )
    
    # Foreign keys
    slice_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("slices.id", ondelete="SET NULL"),
        nullable=True, 
        index=True,
        comment="Reference to the slice this device belongs to"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True, 
        index=True,
        comment="Reference to the user who owns this device"
    )
    
    # Relationships
    slice: Mapped[Optional["Slice"]] = relationship("Slice", back_populates="devices")
    metrics: Mapped[List["Metric"]] = relationship(
        "Metric", 
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="devices")
    
    def __repr__(self) -> str:
        return f"<Device(id='{self.id}', name='{self.name}', type='{self.type}')>"
    
    def is_online(self) -> bool:
        """Check if the device is currently online."""
        if not self.last_seen:
            return False
        return (datetime.now(timezone.utc) - self.last_seen) < timedelta(minutes=5)
    
    def update_status(self, new_status: str) -> None:
        """Update the device status and last seen timestamp."""
        self.status = new_status
        self.last_seen = datetime.now(timezone.utc)

class Metric(Base):
    """Network performance metrics model.
    
    Tracks various performance and resource utilization metrics for network slices and devices.
    """
    __tablename__ = "metrics"
    
    # Primary key and timestamp
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        index=True,
        comment="Unique identifier for the metric record"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        index=True, 
        nullable=False,
        comment="Timestamp when the metric was recorded"
    )
    
    # Performance metrics
    throughput: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Network throughput in Mbps (Megabits per second)"
    )
    latency: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Network latency in milliseconds"
    )
    packet_loss: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Packet loss percentage (0-100)"
    )
    
    # Resource utilization
    cpu_usage: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="CPU utilization percentage (0-100)"
    )
    memory_usage: Mapped[Optional[float]] = mapped_column(
        Float, 
        nullable=True,
        comment="Memory utilization percentage (0-100)"
    )
    
    # Foreign keys
    slice_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("slices.id", ondelete="CASCADE"),
        nullable=True, 
        index=True,
        comment="Reference to the associated network slice"
    )
    device_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=True, 
        index=True,
        comment="Reference to the associated device"
    )
    
    # Relationships
    slice: Mapped[Optional["Slice"]] = relationship("Slice", back_populates="metrics")
    device: Mapped[Optional["Device"]] = relationship("Device", back_populates="metrics")
    
    # Additional metadata
    metrics_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, 
        nullable=True,
        comment="Additional metrics or tags in JSON format"
    )
    
    def __repr__(self) -> str:
        return f"<Metric(id={self.id}, type='{self.metric_type}', value={self.metric_value}')>"
    
    @property
    def metric_type(self) -> str:
        """Determine the type of metric based on available fields."""
        if self.throughput is not None:
            return "throughput"
        elif self.latency is not None:
            return "latency"
        elif self.packet_loss is not None:
            return "packet_loss"
        elif self.cpu_usage is not None:
            return "cpu_usage"
        elif self.memory_usage is not None:
            return "memory_usage"
        return "unknown"
    
    @property
    def metric_value(self) -> Optional[float]:
        """Get the metric value based on the metric type."""
        return getattr(self, self.metric_type, None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the metric to a dictionary.
        
        Returns:
            Dict[str, Any]: A dictionary representation of the metric
        """
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "type": self.metric_type,
            "value": self.metric_value,
            "slice_id": self.slice_id,
            "device_id": self.device_id,
            "metadata": self.metrics_metadata or {}
        }


class Alert(Base):
    """Alert model for system and network events.
    
    Tracks important events and issues in the network that require attention.
    """
    __tablename__ = "alerts"
    
    id: Mapped[int] = mapped_column(
        Integer, 
        primary_key=True, 
        index=True,
        comment="Unique identifier for the alert"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        index=True, 
        nullable=False,
        comment="Timestamp when the alert was generated"
    )
    level: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default=Level.INFO,
        comment="Alert severity level (critical, warning, info)"
    )
    message: Mapped[str] = mapped_column(
        Text, 
        nullable=False,
        comment="Detailed description of the alert"
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False,
        comment="Whether the alert has been resolved"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), 
        nullable=True,
        comment="Timestamp when the alert was resolved"
    )
    entity_type: Mapped[str] = mapped_column(
        String(20), 
        nullable=False,
        comment="Type of entity this alert is about (slice, device, system, network)"
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), 
        nullable=False,
        comment="ID of the related entity"
    )
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True, 
        index=True,
        comment="User who owns or is responsible for this alert"
    )
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, 
        nullable=True,
        comment="Additional context or metadata for the alert in JSON format"
    )
    
    # Relationships
    owner: Mapped[Optional["User"]] = relationship("User", back_populates="alerts")
    
    def __repr__(self):
        return f"<Alert(id={self.id}, level={self.level}, message={self.message[:50]}...)>"
    
    def is_active(self) -> bool:
        """Check if the alert is currently active (not resolved)."""
        return not self.resolved
    
    def resolve(self):
        """Mark the alert as resolved with the current timestamp."""
        self.resolved = True
        self.resolved_at = datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the alert to a dictionary representation.
        
        Returns:
            Dict[str, Any]: A dictionary containing alert details
        """
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'level': self.level,
            'message': self.message,
            'resolved': self.resolved,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'owner_id': self.owner_id,
            'device_id': self.device_id,
            'context': self.context or {}
        }


class SliceKPI(Base):
    """Key Performance Indicators (KPIs) for network slices.
    
    Tracks aggregated performance metrics for network slices over time.
    Used for historical analysis and reporting.
    """
    __tablename__ = "slice_kpis"
    
    # Primary key and timestamp
    id = Column(Integer, primary_key=True, index=True,
              comment="Unique identifier for the KPI record")
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False,
                     comment="Timestamp when the KPI was recorded")
    
    # Performance metrics
    latency = Column(Float, nullable=True,
                   comment="Average latency in milliseconds")
    throughput = Column(Float, nullable=True,
                      comment="Average throughput in Mbps")
    connected_devices = Column(Integer, default=0, nullable=False,
                            comment="Number of connected devices")
    
    # Additional metrics
    packet_loss = Column(Float, nullable=True,
                       comment="Average packet loss percentage (0-100)")
    availability = Column(Float, nullable=True,
                        comment="Slice availability percentage (0-100)")
    
    # Foreign key to Slice
    slice_id = Column(String(36), ForeignKey("slices.id", ondelete="CASCADE"),
                    nullable=False, index=True,
                    comment="Reference to the associated network slice")
    
    # Relationships
    slice = relationship("Slice", back_populates="kpis")
    
    # Additional metadata
    kpi_metadata = Column(JSON, nullable=True,
                       comment="Additional KPI data in JSON format")
    
    def __repr__(self) -> str:
        return f"<SliceKPI(id={self.id}, slice_id='{self.slice_id}', timestamp='{self.timestamp}')>"
    
    @property
    def is_healthy(self) -> bool:
        """Check if the slice KPIs are within healthy thresholds."""
        # Define your health check logic here
        if self.latency and self.latency > 100:  # Example threshold
            return False
        if self.packet_loss and self.packet_loss > 5:  # 5% packet loss
            return False
        return True
    
    def to_dict(self) -> dict:
        """Convert KPI to dictionary representation."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "latency": self.latency,
            "throughput": self.throughput,
            "connected_devices": self.connected_devices,
            "packet_loss": self.packet_loss,
            "availability": self.availability,
            "slice_id": self.slice_id,
            "is_healthy": self.is_healthy,
            "kpi_metadata": self.kpi_metadata or {}
        }
