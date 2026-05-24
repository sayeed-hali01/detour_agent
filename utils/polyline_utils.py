import math
import polyline

def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decodes an encoded Google Maps polyline string to a list of (latitude, longitude) coordinates.
    
    Args:
        encoded: The polyline string.
        
    Returns:
        A list of tuples containing (latitude, longitude) coordinates.
    """
    if not encoded:
        return []
    try:
        return polyline.decode(encoded)
    except Exception as e:
        # Fallback or error logging
        print(f"Error decoding polyline: {e}")
        return []

def sample_coords_from_polyline(coords: list[tuple[float, float]], sample_interval: int = 15) -> list[tuple[float, float]]:
    """Samples coordinates from a list of coordinates to reduce the density.
    
    Args:
        coords: The list of (latitude, longitude) coordinate tuples.
        sample_interval: Step interval for sampling.
        
    Returns:
        A list of sampled (latitude, longitude) coordinate tuples.
    """
    if not coords:
        return []
    
    sampled = [coords[i] for i in range(0, len(coords), sample_interval)]
    
    # Ensure the last coordinate is included so we cover the destination area
    if coords[-1] not in sampled:
        sampled.append(coords[-1])
        
    return sampled

def haversine_distance(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Calculates the great-circle distance between two points in kilometers.
    
    Args:
        coord1: A tuple of (latitude, longitude).
        coord2: A tuple of (latitude, longitude).
        
    Returns:
        The distance in kilometers.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371.0  # Earth's radius in kilometers
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c
