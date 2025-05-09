class_name Mob
extends CharacterBody2D


@export var stats: Dictionary = {
	"health": 10.0
}


func _ready() -> void:
	position = position.snappedf(Global.TILE_SIZE)
