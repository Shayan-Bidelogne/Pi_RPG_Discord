extends Camera2D


func _ready() -> void:
	if owner is Map:
		set_camera_limits(owner.main_tile_map)


func set_camera_limits(tile_map: TileMapLayer):
	var map_limits = tile_map.get_used_rect()
	var map_cellsize = tile_map.tile_set.tile_size
	limit_left = map_limits.position.x * map_cellsize.x
	limit_right = map_limits.end.x * map_cellsize.x
	limit_top = map_limits.position.y * map_cellsize.y
	limit_bottom = map_limits.end.y * map_cellsize.y
