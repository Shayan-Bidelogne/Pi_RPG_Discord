extends Control


func _enter_tree() -> void:
	if not OS.has_feature("debug"):
		queue_free()
