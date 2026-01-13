Param(
  [string]$ModeA = "runs/modeA.jsonl",
  [string]$ModeB = "runs/modeB.jsonl"
)

function Run-Anim {
  param([string]$LogPath, [string]$OutBase)
  if (Test-Path $LogPath) {
    python tools/animate_ring.py --log $LogPath --out "runs/anim_ring_$OutBase.mp4"
    python tools/animate_orbit.py --log $LogPath --out "runs/anim_orbit_$OutBase.mp4"
  } else {
    Write-Host "Log not found: $LogPath"
  }
}

Run-Anim -LogPath $ModeA -OutBase "modeA"
Run-Anim -LogPath $ModeB -OutBase "modeB"
