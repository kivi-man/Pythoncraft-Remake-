"""
Block metadata system for storing additional block data like water levels
"""


class BlockMetadata:
    def __init__(self):
        # Dictionary mapping (x, y, z) -> metadata dict
        self.metadata = {}
    
    def set_water_level(self, position, level):
        """Set water level (0-7) for a water block"""
        x, y, z = position
        pos_key = (x, y, z)
        
        if pos_key not in self.metadata:
            self.metadata[pos_key] = {}
        
        self.metadata[pos_key]['water_level'] = level
    
    def get_water_level(self, position):
        """Get water level for a water block, returns 0 if not set"""
        x, y, z = position
        pos_key = (x, y, z)
        
        if pos_key in self.metadata and 'water_level' in self.metadata[pos_key]:
            return self.metadata[pos_key]['water_level']
        
        return 0  # Default to source block
    
    def remove_metadata(self, position):
        """Remove all metadata for a position"""
        x, y, z = position
        pos_key = (x, y, z)
        
        if pos_key in self.metadata:
            del self.metadata[pos_key]
    
    def has_metadata(self, position):
        """Check if position has any metadata"""
        x, y, z = position
        return (x, y, z) in self.metadata
