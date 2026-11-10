import { Link } from 'react-router-dom'
import heroBg from '../assets/hero-bg.jpg'
import { useAuth } from '../context/AuthContext'

export function Landing() {
  const { user, profile } = useAuth()

  return (
    <div className="relative h-screen min-h-[640px] w-full overflow-hidden bg-[#19132c] text-white select-none">
      {/* Full-bleed Sunset Pixel Art Background */}
      <img
        src={heroBg}
        alt="Golden hour landscape overlooking a city skyline"
        className="absolute inset-0 h-full w-full object-cover object-center"
      />

      {/* Left-side atmospheric gradient wash matching the reference:
          Darkens the left sky/horizon behind the typography while leaving the sun,
          skyline, right tree, and bottom-left sleeping cat vivid and unobstructed */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background: `
            radial-gradient(75% 75% at 14% 38%, rgba(25, 20, 48, 0.72) 0%, rgba(25, 20, 48, 0.42) 48%, rgba(25, 20, 48, 0) 100%),
            linear-gradient(90deg, rgba(23, 18, 44, 0.58) 0%, rgba(23, 18, 44, 0.25) 38%, rgba(23, 18, 44, 0) 62%)
          `,
        }}
      />

      {/* Content Container */}
      <div className="relative z-10 mx-auto flex h-full max-w-[1440px] flex-col justify-between px-8 py-7 sm:px-14 sm:py-9 lg:px-20 lg:py-10">
        {/* Top Navigation */}
        <header className="flex items-center justify-between">
          {/* Brand Logo: 4-point star + Nudge */}
          <Link
            to="/"
            className="inline-flex items-center gap-2.5 text-white focus:outline-none group"
          >
            <svg
              viewBox="0 0 24 24"
              fill="currentColor"
              className="h-6 w-6 text-white transition-transform duration-300 group-hover:scale-110"
              aria-hidden="true"
            >
              <path d="M12 1.5C12.7 7.1 16.9 11.3 22.5 12C16.9 12.7 12.7 16.9 12 22.5C11.3 16.9 7.1 12.7 1.5 12C7.1 11.3 11.3 7.1 12 1.5Z" />
            </svg>
            <span className="font-sans text-[19px] font-semibold tracking-[-0.015em] text-white">
              Nudge
            </span>
          </Link>

          {/* Right Nav Links + CTA Pill */}
          <nav className="flex items-center gap-7 sm:gap-9">
            <Link
              to="/projects"
              className="hidden sm:inline-block font-sans text-[15px] font-normal text-white/90 transition-colors hover:text-white"
            >
              Projects
            </Link>
            {user ? (
              <Link
                to="/projects"
                className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 font-sans text-[14px] font-semibold tracking-[-0.01em] text-[#141418] shadow-[0_4px_20px_rgba(0,0,0,0.2)] transition-all hover:bg-white/92 hover:scale-[1.02] active:scale-[0.99]"
              >
                <span>{profile?.display_name || 'Open Hub'}</span>
                <span aria-hidden="true" className="text-[15px] leading-none">
                  &rarr;
                </span>
              </Link>
            ) : (
              <>
                <Link
                  to="/auth"
                  className="hidden sm:inline-block font-sans text-[15px] font-normal text-white/90 transition-colors hover:text-white"
                >
                  Sign In
                </Link>
                <Link
                  to="/auth?mode=signup"
                  className="inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 font-sans text-[14px] font-semibold tracking-[-0.01em] text-[#141418] shadow-[0_4px_20px_rgba(0,0,0,0.2)] transition-all hover:bg-white/92 hover:scale-[1.02] active:scale-[0.99]"
                >
                  <span>Get Started</span>
                  <span aria-hidden="true" className="text-[15px] leading-none">
                    &rarr;
                  </span>
                </Link>
              </>
            )}
          </nav>
        </header>

        {/* Center-Left Hero Typography & Actions */}
        <main className="my-auto pb-12 sm:pb-16 lg:pb-20">
          <div className="max-w-[620px]">
            <h1 className="text-white">
              <span className="block font-sans text-[3.4rem] sm:text-[4.65rem] lg:text-[5.4rem] font-medium leading-[1.04] tracking-[-0.035em] drop-shadow-[0_2px_24px_rgba(16,11,32,0.35)]">
                Build. Learn.
              </span>
              <span className="block font-serif italic font-normal text-[3.8rem] sm:text-[5.25rem] lg:text-[6.15rem] leading-[0.98] tracking-[-0.01em] text-white/95 drop-shadow-[0_2px_24px_rgba(16,11,32,0.35)]">
                Go Further.
              </span>
            </h1>

            <p className="mt-5 sm:mt-6 max-w-[430px] font-sans text-[16px] sm:text-[18px] font-normal leading-[1.55] tracking-[-0.01em] text-white/85 drop-shadow-[0_1px_12px_rgba(14,9,28,0.5)]">
              Hands-on, real-world projects to master
              <br className="hidden sm:inline" /> modern development — with AI by your side.
            </p>

            {/* Primary & Secondary CTAs */}
            <div className="mt-8 sm:mt-9 flex flex-wrap items-center gap-6">
              <Link
                to={user ? '/projects' : '/auth'}
                className="inline-flex items-center gap-2.5 rounded-full bg-white px-7 py-3.5 font-sans text-[15px] font-semibold tracking-[-0.01em] text-[#141418] shadow-[0_8px_28px_rgba(12,8,24,0.32)] transition-all hover:bg-white/92 hover:scale-[1.02] active:scale-[0.99]"
              >
                <span>Start Learning</span>
                <span aria-hidden="true" className="text-[16px] leading-none">
                  &rarr;
                </span>
              </Link>

              <Link
                to="/projects"
                className="group inline-flex items-center gap-2.5 font-sans text-[15px] font-medium text-white/90 transition-colors hover:text-white"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full border border-white/40 bg-white/10 backdrop-blur-sm transition-colors group-hover:border-white/70 group-hover:bg-white/20">
                  <svg
                    viewBox="0 0 12 12"
                    fill="currentColor"
                    className="h-2.5 w-2.5 translate-x-[0.5px] text-white"
                    aria-hidden="true"
                  >
                    <path d="M3 2.2L9.5 6L3 9.8V2.2Z" />
                  </svg>
                </span>
                <span className="drop-shadow-[0_1px_8px_rgba(14,9,28,0.5)]">
                  Explore Projects
                </span>
              </Link>
            </div>
          </div>
        </main>

        {/* Bottom Spacer to keep vertical balance above the sleeping cat */}
        <div className="h-4" aria-hidden="true" />
      </div>
    </div>
  )
}

export default Landing
