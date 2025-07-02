"""
Compression utilities for the 5G Slice Manager.

This module provides functions for compressing and decompressing data
using various algorithms to optimize network transfer and storage.
"""

import gzip
import lzma
import zlib
import json
import pickle
from enum import Enum, auto
from typing import Any, Dict, Optional, Union, Tuple

from app.core.config import settings


class CompressionAlgorithm(Enum):
    """Supported compression algorithms."""
    NONE = auto()
    GZIP = auto()
    LZMA = auto()
    ZLIB = auto()
    
    @classmethod
    def from_string(cls, name: str) -> 'CompressionAlgorithm':
        """Get compression algorithm from string name."""
        name = name.upper()
        if name == 'NONE':
            return cls.NONE
        elif name == 'GZIP':
            return cls.GZIP
        elif name == 'LZMA':
            return cls.LZMA
        elif name == 'ZLIB':
            return cls.ZLIB
        else:
            raise ValueError(f"Unsupported compression algorithm: {name}")


class Compressor:
    """Compresses and decompresses data using the specified algorithm."""
    
    def __init__(
        self,
        algorithm: Union[CompressionAlgorithm, str] = CompressionAlgorithm.GZIP,
        level: Optional[int] = None,
    ):
        """Initialize the compressor.
        
        Args:
            algorithm: Compression algorithm to use
            level: Compression level (1-9, higher means better compression but slower)
        """
        if isinstance(algorithm, str):
            algorithm = CompressionAlgorithm.from_string(algorithm)
            
        self.algorithm = algorithm
        self.level = level or settings.COMPRESSION_LEVEL
        
        # Validate compression level
        if self.level is not None:
            if not 1 <= self.level <= 9:
                raise ValueError("Compression level must be between 1 and 9")
    
    def compress(
        self,
        data: Union[str, bytes, Dict[str, Any]],
        encoding: str = 'utf-8',
    ) -> bytes:
        """Compress data using the configured algorithm.
        
        Args:
            data: Data to compress (string, bytes, or JSON-serializable dict)
            encoding: Encoding to use for string data
            
        Returns:
            Compressed data as bytes
        """
        # Convert input to bytes if needed
        if isinstance(data, str):
            data_bytes = data.encode(encoding)
        elif isinstance(data, dict):
            data_bytes = json.dumps(data).encode(encoding)
        else:
            data_bytes = data
        
        # Apply compression
        if self.algorithm == CompressionAlgorithm.NONE:
            return data_bytes
        elif self.algorithm == CompressionAlgorithm.GZIP:
            return gzip.compress(data_bytes, compresslevel=self.level)
        elif self.algorithm == CompressionAlgorithm.LZMA:
            return lzma.compress(
                data_bytes,
                preset=self.level,
                format=lzma.FORMAT_XZ,
            )
        elif self.algorithm == CompressionAlgorithm.ZLIB:
            return zlib.compress(data_bytes, level=self.level)
        else:
            raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")
    
    def decompress(
        self,
        data: bytes,
        encoding: str = 'utf-8',
        as_json: bool = False,
    ) -> Union[str, bytes, Dict[str, Any]]:
        """Decompress data using the configured algorithm.
        
        Args:
            data: Compressed data as bytes
            encoding: Encoding to use for string output
            as_json: Whether to parse the output as JSON
            
        Returns:
            Decompressed data (bytes, str, or dict if as_json=True)
        """
        # Detect compression algorithm if not specified
        if self.algorithm == CompressionAlgorithm.NONE:
            decompressed = data
        elif self.algorithm == CompressionAlgorithm.GZIP:
            decompressed = gzip.decompress(data)
        elif self.algorithm == CompressionAlgorithm.LZMA:
            decompressed = lzma.decompress(data)
        elif self.algorithm == CompressionAlgorithm.ZLIB:
            decompressed = zlib.decompress(data)
        else:
            raise ValueError(f"Unsupported compression algorithm: {self.algorithm}")
        
        # Convert to desired output format
        if as_json:
            return json.loads(decompressed.decode(encoding))
        elif encoding:
            try:
                return decompressed.decode(encoding)
            except UnicodeDecodeError:
                return decompressed
        else:
            return decompressed
    
    @staticmethod
    def detect_algorithm(data: bytes) -> Optional[CompressionAlgorithm]:
        """Detect the compression algorithm used for the given data.
        
        Args:
            data: Compressed data to analyze
            
        Returns:
            Detected compression algorithm or None if unknown
        """
        # Check for GZIP magic number
        if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
            return CompressionAlgorithm.GZIP
        
        # Check for XZ magic number
        if len(data) >= 6 and data[0] == 0xFD and data[1:4] == b'7zXZ' and data[4:6] == b'\x00\x00':
            return CompressionAlgorithm.LZMA
        
        # Check for ZLIB header (first byte: CMF, second byte: FLG)
        if len(data) >= 2:
            cmf = data[0]
            flg = data[1]
            
            # Check for zlib header (RFC 1950)
            if (cmf & 0x0F) == 8:  # CM = 8 means "deflate"
                if (cmf * 256 + flg) % 31 == 0:  # FCHECK must be valid
                    return CompressionAlgorithm.ZLIB
        
        return None


def compress(
    data: Union[str, bytes, Dict[str, Any]],
    algorithm: Union[CompressionAlgorithm, str] = 'gzip',
    level: Optional[int] = None,
) -> bytes:
    """Compress data using the specified algorithm.
    
    Args:
        data: Data to compress (string, bytes, or JSON-serializable dict)
        algorithm: Compression algorithm to use
        level: Compression level (1-9)
        
    Returns:
        Compressed data as bytes
    """
    compressor = Compressor(algorithm=algorithm, level=level)
    return compressor.compress(data)


def decompress(
    data: bytes,
    algorithm: Optional[Union[CompressionAlgorithm, str]] = None,
    encoding: Optional[str] = 'utf-8',
    as_json: bool = False,
) -> Union[str, bytes, Dict[str, Any]]:
    """Decompress data using the specified or detected algorithm.
    
    Args:
        data: Compressed data as bytes
        algorithm: Compression algorithm to use (None for auto-detect)
        encoding: Encoding to use for string output
        as_json: Whether to parse the output as JSON
        
    Returns:
        Decompressed data (bytes, str, or dict if as_json=True)
    """
    if algorithm is None:
        detected = Compressor.detect_algorithm(data)
        if detected is None:
            raise ValueError("Could not detect compression algorithm")
        algorithm = detected
    
    compressor = Compressor(algorithm=algorithm)
    return compressor.decompress(data, encoding=encoding, as_json=as_json)


def estimate_compression_ratio(
    data: Union[str, bytes, Dict[str, Any]],
    algorithm: Union[CompressionAlgorithm, str] = 'gzip',
    level: Optional[int] = None,
) -> float:
    """Estimate the compression ratio for the given data.
    
    Args:
        data: Data to compress (string, bytes, or JSON-serializable dict)
        algorithm: Compression algorithm to use
        level: Compression level (1-9)
        
    Returns:
        Compression ratio (original_size / compressed_size)
    """
    if isinstance(data, str):
        original_size = len(data.encode('utf-8'))
    elif isinstance(data, dict):
        original_size = len(json.dumps(data).encode('utf-8'))
    else:
        original_size = len(data)
    
    if original_size == 0:
        return 1.0
    
    compressed = compress(data, algorithm=algorithm, level=level)
    compressed_size = len(compressed)
    
    return original_size / compressed_size


# Example usage
if __name__ == "__main__":
    # Example data
    sample_data = {
        "timestamp": "2023-01-01T12:00:00Z",
        "device_id": "device-123",
        "metrics": {
            "cpu_usage": 45.2,
            "memory_usage": 12345678,
            "network_in": 1024,
            "network_out": 2048,
        },
        "tags": ["production", "high-priority"],
    }
    
    # Create a compressor
    compressor = Compressor(algorithm='gzip', level=6)
    
    # Compress the data
    compressed = compressor.compress(sample_data)
    print(f"Original size: {len(json.dumps(sample_data).encode('utf-8'))} bytes")
    print(f"Compressed size: {len(compressed)} bytes")
    
    # Decompress the data
    decompressed = compressor.decompress(compressed, as_json=True)
    print(f"Decompressed data matches original: {decompressed == sample_data}")
