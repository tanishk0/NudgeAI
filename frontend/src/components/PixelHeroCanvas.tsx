import { useEffect, useRef, useState } from 'react'

interface PixelHeroCanvasProps {
  src: string
  alt?: string
  className?: string
}

const ZONE_STATIC = 0
const ZONE_LEAF = 1
const ZONE_WATER = 2
const ZONE_GRASS = 3
const ZONE_CAT = 4
const ZONE_FLOWER = 5

// 4x4 Bayer ordered dithering matrix (normalized -0.5 .. +0.5)
const BAYER_4X4 = [
  -0.46875, 0.03125, -0.34375, 0.15625,
  0.28125, -0.21875, 0.40625, -0.09375,
  -0.28125, 0.21875, -0.40625, 0.09375,
  0.46875, -0.03125, 0.34375, -0.15625,
]

interface LeafParticle {
  x: number
  y: number
  vx: number
  vy: number
  phase: number
  life: number
  maxLife: number
  color: [number, number, number]
}

interface FireflyParticle {
  x: number
  y: number
  baseX: number
  baseY: number
  phase: number
  speed: number
  color: [number, number, number]
}

interface BirdParticle {
  x: number
  y: number
  speed: number
  phase: number
}

function quantizeChannel(value: number, dither: number, levels: number): number {
  const step = 255 / (levels - 1)
  const q = Math.round((value + dither * step * 0.45) / step) * step
  return q < 0 ? 0 : q > 255 ? 255 : q
}

function isFoliageColor(r: number, g: number, b: number): boolean {
  // Olive, golden-green, mossy green, and deep forest shadow tones
  return g >= b + 12 && (g >= r - 18 || (r > 120 && g > 110 && b < 75))
}

function isFlowerColor(r: number, g: number, b: number): boolean {
  const chroma = Math.max(r, g, b) - Math.min(r, g, b)
  // Purple / lavender / violet petals (bottom-left patch & accents)
  const isPurple = b > g + 18 && r > 80 && b > 110 && chroma > 28
  // Coral / pink / rose wildflowers (right hillside under tree & center)
  const isCoralPink = r > 155 && r > g + 28 && chroma > 35
  // Bright white / cream daisy petals
  const isWhitePetal = r > 185 && g > 175 && b > 150
  // Warm golden-yellow flower centers & buttercups
  const isYellowPetal = r > 195 && g > 160 && b < 115 && chroma > 70
  return isPurple || isCoralPink || isWhitePetal || isYellowPetal
}

function isGrassColor(r: number, g: number, b: number): boolean {
  return g >= b + 10 && g >= r - 25
}

function isCatColor(r: number, g: number, b: number): boolean {
  // Warm ginger/orange fur or cream/white chest fur (distinct from cool purple rock)
  const isGinger = r > 135 && g > 65 && b < 95 && r - b > 45
  const isCream = r > 175 && g > 160 && b > 140
  return isGinger || isCream
}

export function PixelHeroCanvas({
  src,
  alt = 'Animated pixel art landscape',
  className = '',
}: PixelHeroCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    const canvas = canvasRef.current
    if (!container || !canvas) return

    const ctx = canvas.getContext('2d', { alpha: false })
    if (!ctx) return

    let disposed = false
    let rafId = 0
    let imgLoaded = false

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = src

    const offscreen = document.createElement('canvas')
    const offCtx = offscreen.getContext('2d', { willReadFrequently: true })
    if (!offCtx) return

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let vw = 0
    let vh = 0
    let baseData = new Uint8ClampedArray(0)
    let frameData = new Uint8ClampedArray(0)
    let imageDataObj: ImageData | null = null
    let zoneMask = new Uint8Array(0)
    let uCoords = new Float32Array(0)

    let leaves: LeafParticle[] = []
    let fireflies: FireflyParticle[] = []
    let birds: BirdParticle[] = []

    const leafPalette: [number, number, number][] = [
      [182, 162, 54],
      [148, 154, 48],
      [212, 174, 72],
      [112, 126, 44],
    ]

    const spawnLeaf = (w: number, h: number, randomLife = false): LeafParticle => {
      const startX = w * (0.46 + Math.random() * 0.5)
      const startY = h * (0.04 + Math.random() * 0.22)
      const maxLife = 6 + Math.random() * 5
      return {
        x: startX,
        y: startY,
        vx: -5.2 - Math.random() * 5.6,
        vy: 6.8 + Math.random() * 4.8,
        phase: Math.random() * Math.PI * 2,
        life: randomLife ? Math.random() * maxLife : 0,
        maxLife,
        color: leafPalette[Math.floor(Math.random() * leafPalette.length)],
      }
    }

    const initParticles = (w: number, h: number) => {
      leaves = Array.from({ length: 11 }, () => spawnLeaf(w, h, true))

      fireflies = Array.from({ length: 16 }, () => {
        const bx = w * (0.08 + Math.random() * 0.84)
        const by = h * (0.58 + Math.random() * 0.36)
        return {
          x: bx,
          y: by,
          baseX: bx,
          baseY: by,
          phase: Math.random() * Math.PI * 2,
          speed: 0.7 + Math.random() * 0.8,
          color: Math.random() > 0.35 ? [255, 224, 130] : [255, 194, 118],
        }
      })

      birds = [
        { x: w * 0.37, y: h * 0.35, speed: 2.8, phase: 0.2 },
        { x: w * 0.43, y: h * 0.33, speed: 3.1, phase: 1.8 },
        { x: w * 0.61, y: h * 0.27, speed: 2.5, phase: 3.4 },
      ]
    }

    const buildPixelScene = () => {
      if (!imgLoaded || disposed) return
      const rect = container.getBoundingClientRect()
      if (rect.width === 0 || rect.height === 0) return

      // Fine HD pixel-art grid (~680-960 virtual px wide on desktop)
      const pixelSize = rect.width >= 1024 ? 2 : rect.width >= 640 ? 1.75 : 1.5
      vw = Math.max(240, Math.round(rect.width / pixelSize))
      vh = Math.max(180, Math.round(rect.height / pixelSize))

      canvas.width = vw
      canvas.height = vh
      ctx.imageSmoothingEnabled = false

      offscreen.width = vw
      offscreen.height = vh
      offCtx.imageSmoothingEnabled = true
      offCtx.imageSmoothingQuality = 'medium'

      // Object-cover crop math matching object-cover object-center
      const scale = Math.max(vw / img.width, vh / img.height)
      const drawW = img.width * scale
      const drawH = img.height * scale
      const offsetX = (vw - drawW) / 2
      const offsetY = (vh - drawH) / 2

      offCtx.clearRect(0, 0, vw, vh)
      offCtx.drawImage(img, offsetX, offsetY, drawW, drawH)

      const raw = offCtx.getImageData(0, 0, vw, vh)
      const srcBytes = raw.data
      const totalPixels = vw * vh

      baseData = new Uint8ClampedArray(totalPixels * 4)
      frameData = new Uint8ClampedArray(totalPixels * 4)
      zoneMask = new Uint8Array(totalPixels)
      uCoords = new Float32Array(totalPixels)
      imageDataObj = new ImageData(frameData, vw, vh)

      const quantLevels = 28

      for (let y = 0; y < vh; y++) {
        const v = (y - offsetY) / drawH
        for (let x = 0; x < vw; x++) {
          const idx = y * vw + x
          const p = idx * 4
          const u = (x - offsetX) / drawW
          uCoords[idx] = u

          const bayer = BAYER_4X4[(y & 3) * 4 + (x & 3)]
          const r = quantizeChannel(srcBytes[p], bayer, quantLevels)
          const g = quantizeChannel(srcBytes[p + 1], bayer, quantLevels)
          const b = quantizeChannel(srcBytes[p + 2], bayer, quantLevels)

          baseData[p] = r
          baseData[p + 1] = g
          baseData[p + 2] = b
          baseData[p + 3] = 255

          // Classify scene zones in normalized image coordinates
          let zone = ZONE_STATIC

          const inTopCanopy = u > 0.4 && v >= 0 && v < 0.34
          const inRightTrees = u > 0.56 && v >= 0.24 && v < 0.66
          const inLeftBush = u >= 0 && u < 0.16 && v > 0.3 && v < 0.62
          const inCatBox = u >= 0.155 && u <= 0.305 && v >= 0.79 && v <= 0.905
          const inRockBox = u >= 0.11 && u <= 0.345 && v >= 0.84 && v <= 0.99
          const inWaterBox = u >= 0.24 && u <= 0.56 && v >= 0.615 && v <= 0.755
          const inFenceBox = u < 0.26 && v >= 0.57 && v <= 0.74
          const inTrunkBox = u > 0.85 && v < 0.62

          if ((inTopCanopy || inRightTrees || inLeftBush) && !inTrunkBox && isFoliageColor(r, g, b)) {
            zone = ZONE_LEAF
          } else if (inWaterBox && r > 90 && g > 60 && b < 140) {
            zone = ZONE_WATER
          } else if (inCatBox && isCatColor(r, g, b)) {
            zone = ZONE_CAT
          } else if (
            v >= 0.54 &&
            !inCatBox &&
            !inRockBox &&
            !inFenceBox &&
            !inTrunkBox &&
            isFlowerColor(r, g, b)
          ) {
            zone = ZONE_FLOWER
          } else if (
            v >= 0.56 &&
            !inCatBox &&
            !inFenceBox &&
            !inTrunkBox &&
            isGrassColor(r, g, b)
          ) {
            zone = ZONE_GRASS
          }

          zoneMask[idx] = zone
        }
      }

      initParticles(vw, vh)
      frameData.set(baseData)
      ctx.putImageData(imageDataObj, 0, 0)
      setReady(true)
    }

    let lastTime = performance.now()
    let accumulator = 0
    const stepInterval = 1000 / 24 // Crisp 24fps pixel-art cadence

    const renderFrame = (now: number) => {
      if (disposed) return
      rafId = requestAnimationFrame(renderFrame)

      const dtMs = Math.min(100, now - lastTime)
      lastTime = now
      accumulator += dtMs
      if (accumulator < stepInterval) return
      const dt = accumulator / 1000
      accumulator = 0

      if (!imageDataObj || vw === 0 || vh === 0) return

      const t = now * 0.001
      frameData.set(baseData)

      // 1. Pixel-grid environmental animations
      for (let y = 2; y < vh - 2; y++) {
        const rowOffset = y * vw
        for (let x = 2; x < vw - 2; x++) {
          const idx = rowOffset + x
          const zone = zoneMask[idx]
          if (zone === ZONE_STATIC) continue

          const p = idx * 4

          if (zone === ZONE_LEAF) {
            // Subtle organic rustle across tree canopy & bushes
            const wave =
              Math.sin(t * 2.2 + x * 0.22 + y * 0.19) +
              0.6 * Math.sin(t * 1.15 - x * 0.07 + y * 0.11)

            if (wave > 0.7 || wave < -0.7) {
              const dx = wave > 0 ? 1 : -1
              const srcIdx = idx + dx
              if (zoneMask[srcIdx] === ZONE_LEAF) {
                const sp = srcIdx * 4
                frameData[p] = baseData[sp]
                frameData[p + 1] = baseData[sp + 1]
                frameData[p + 2] = baseData[sp + 2]
              }
            }

            // Gentle sunlit leaf-tip shimmer
            const shimmer = Math.sin(t * 1.7 + x * 0.35 + y * 0.25)
            if (shimmer > 0.85) {
              frameData[p] = Math.min(255, frameData[p] + 8)
              frameData[p + 1] = Math.min(255, frameData[p + 1] + 8)
            }
          } else if (zone === ZONE_WATER) {
            // Gentle horizontal water ripple + golden sun glint
            const ripple = Math.sin(t * 2.5 + y * 0.75 + x * 0.06)
            if (Math.abs(ripple) > 0.6) {
              const dx = ripple > 0 ? 1 : -1
              const srcIdx = idx + dx
              if (zoneMask[srcIdx] === ZONE_WATER) {
                const sp = srcIdx * 4
                frameData[p] = baseData[sp]
                frameData[p + 1] = baseData[sp + 1]
                frameData[p + 2] = baseData[sp + 2]
              }
            }
            const u = uCoords[idx]
            if (u > 0.28 && u < 0.35) {
              const glint = Math.sin(t * 3.4 + y * 1.1 + x * 0.45)
              if (glint > 0.92) {
                frameData[p] = Math.min(255, frameData[p] + 24)
                frameData[p + 1] = Math.min(255, frameData[p + 1] + 20)
                frameData[p + 2] = Math.min(255, frameData[p + 2] + 8)
              }
            }
          } else if (zone === ZONE_FLOWER) {
            // Gentle petal rustle + swaying in the evening breeze
            const rustle =
              Math.sin(t * 2.6 + x * 0.28 + y * 0.24) +
              0.55 * Math.sin(t * 1.4 - x * 0.08 + y * 0.14)
            const gust = Math.sin(t * 1.35 - x * 0.032 + y * 0.04)

            if (gust > 0.62 || rustle > 0.65 || rustle < -0.65) {
              const dx = gust > 0.62 ? -1 : rustle > 0 ? 1 : -1
              const dy = Math.sin(t * 3.1 + x * 0.4 + y * 0.3) > 0.82 ? 1 : 0
              const srcIdx = (y + dy) * vw + (x + dx)
              const srcZone = zoneMask[srcIdx]
              if (srcZone === ZONE_FLOWER || srcZone === ZONE_GRASS) {
                const sp = srcIdx * 4
                frameData[p] = baseData[sp]
                frameData[p + 1] = baseData[sp + 1]
                frameData[p + 2] = baseData[sp + 2]
              }
            }

            // Subtle warm golden-hour shimmer on petal highlights
            const petalGlow = Math.sin(t * 2.0 + x * 0.45 + y * 0.35)
            if (petalGlow > 0.86) {
              frameData[p] = Math.min(255, frameData[p] + 7)
              frameData[p + 1] = Math.min(255, frameData[p + 1] + 6)
              frameData[p + 2] = Math.min(255, frameData[p + 2] + 6)
            }
          } else if (zone === ZONE_GRASS) {
            // Rolling golden-hour breeze across meadow grass & wildflowers
            const gust = Math.sin(t * 1.35 - x * 0.032 + y * 0.04)
            if (gust > 0.68) {
              const srcIdx = idx - 1
              if (zoneMask[srcIdx] === ZONE_GRASS) {
                const sp = srcIdx * 4
                frameData[p] = baseData[sp]
                frameData[p + 1] = baseData[sp + 1]
                frameData[p + 2] = baseData[sp + 2]
              }
            }
          } else if (zone === ZONE_CAT) {
            // Very subtle 1px breathing motion on the sleeping cat
            const breath = Math.sin(t * 1.45)
            if (breath > 0.55) {
              const belowIdx = (y + 1) * vw + x
              if (zoneMask[belowIdx] === ZONE_CAT) {
                const sp = belowIdx * 4
                frameData[p] = baseData[sp]
                frameData[p + 1] = baseData[sp + 1]
                frameData[p + 2] = baseData[sp + 2]
              }
            }
          }
        }
      }

      // 2. Drifting canopy leaves (2x1 pixel leaf)
      for (let i = 0; i < leaves.length; i++) {
        const leaf = leaves[i]
        leaf.life += dt
        if (leaf.life >= leaf.maxLife) {
          leaves[i] = spawnLeaf(vw, vh, false)
          continue
        }
        leaf.x += (leaf.vx + Math.sin(t * 1.8 + leaf.phase) * 3.2) * dt
        leaf.y += leaf.vy * dt

        const px = Math.round(leaf.x)
        const py = Math.round(leaf.y)
        const fade = Math.min(1, leaf.life * 1.5, (leaf.maxLife - leaf.life) * 1.2)
        const alpha = 0.75 * fade
        for (let ox = 0; ox <= 1; ox++) {
          const lx = px + ox
          if (lx >= 0 && lx < vw && py >= 0 && py < vh) {
            const p = (py * vw + lx) * 4
            frameData[p] = Math.round(frameData[p] * (1 - alpha) + leaf.color[0] * alpha)
            frameData[p + 1] = Math.round(frameData[p + 1] * (1 - alpha) + leaf.color[1] * alpha)
            frameData[p + 2] = Math.round(frameData[p + 2] * (1 - alpha) + leaf.color[2] * alpha)
          }
        }
      }

      // 3. Warm golden dusk motes / fireflies over the meadow (2x2 soft pixel glow)
      for (let i = 0; i < fireflies.length; i++) {
        const f = fireflies[i]
        f.x = f.baseX + Math.sin(t * f.speed + f.phase) * 8.5
        f.y = f.baseY + Math.cos(t * f.speed * 0.8 + f.phase) * 4.5

        const glow = 0.5 + 0.5 * Math.sin(t * 2.1 + f.phase * 2)
        if (glow < 0.2) continue

        const px = Math.round(f.x)
        const py = Math.round(f.y)
        const alpha = glow * 0.72
        for (let oy = 0; oy <= 1; oy++) {
          for (let ox = 0; ox <= 1; ox++) {
            const fx = px + ox
            const fy = py + oy
            if (fx >= 0 && fx < vw && fy >= 0 && fy < vh) {
              const p = (fy * vw + fx) * 4
              const weight = ox === 0 && oy === 0 ? alpha : alpha * 0.45
              frameData[p] = Math.min(
                255,
                Math.round(frameData[p] * (1 - weight) + f.color[0] * weight),
              )
              frameData[p + 1] = Math.min(
                255,
                Math.round(frameData[p + 1] * (1 - weight) + f.color[1] * weight),
              )
              frameData[p + 2] = Math.min(
                255,
                Math.round(frameData[p + 2] * (1 - weight) + f.color[2] * weight),
              )
            }
          }
        }
      }

      // 4. Tiny distant pixel birds gliding across the sunset sky
      for (let i = 0; i < birds.length; i++) {
        const b = birds[i]
        b.x += b.speed * dt
        if (b.x > vw * 0.75) {
          b.x = vw * 0.25
        }
        const bx = Math.round(b.x)
        const by = Math.round(b.y + Math.sin(t * 0.9 + b.phase) * 2.2)
        const flap = Math.sin(t * 5.2 + b.phase) > 0 ? -1 : 0

        const birdPts: [number, number][] = [
          [bx, by],
          [bx - 1, by + flap],
          [bx + 1, by + flap],
          [bx - 2, by + flap * 2],
          [bx + 2, by + flap * 2],
        ]
        for (const [px, py] of birdPts) {
          if (px >= 0 && px < vw && py >= 0 && py < vh) {
            const p = (py * vw + px) * 4
            frameData[p] = Math.round(frameData[p] * 0.45 + 68 * 0.55)
            frameData[p + 1] = Math.round(frameData[p + 1] * 0.45 + 42 * 0.55)
            frameData[p + 2] = Math.round(frameData[p + 2] * 0.45 + 58 * 0.55)
          }
        }
      }

      ctx.putImageData(imageDataObj, 0, 0)
    }

    img.onload = () => {
      if (disposed) return
      imgLoaded = true
      buildPixelScene()
      if (!prefersReducedMotion) {
        lastTime = performance.now()
        rafId = requestAnimationFrame(renderFrame)
      }
    }

    const resizeObserver = new ResizeObserver(() => {
      if (imgLoaded) {
        buildPixelScene()
      }
    })
    resizeObserver.observe(container)

    return () => {
      disposed = true
      if (rafId) cancelAnimationFrame(rafId)
      resizeObserver.disconnect()
    }
  }, [src])

  return (
    <div ref={containerRef} className={className} aria-label={alt} role="img">
      <canvas
        ref={canvasRef}
        className={`h-full w-full transition-opacity duration-500 ${
          ready ? 'opacity-100' : 'opacity-0'
        }`}
        style={{ imageRendering: 'pixelated' }}
      />
    </div>
  )
}
