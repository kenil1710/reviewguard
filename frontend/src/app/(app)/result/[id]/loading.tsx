export default function Loading() {
  return (
    <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <div className="skeleton h-4 w-24 rounded-full" />
      <div className="mt-5 grid gap-6 lg:grid-cols-[1.45fr_1fr]">
        <div className="card p-7">
          <div className="flex gap-2">
            <div className="skeleton h-6 w-24 rounded-full" />
            <div className="skeleton h-6 w-28 rounded-full" />
          </div>
          <div className="skeleton mt-4 h-7 w-3/4 rounded-lg" />
          <div className="skeleton mt-2 h-3 w-1/2 rounded-full" />
          <div className="mt-5 flex gap-3">
            <div className="skeleton h-9 w-44 rounded-lg" />
            <div className="skeleton h-9 w-44 rounded-lg" />
          </div>
        </div>
        <div className="card grid place-items-center p-7">
          <div className="skeleton h-[210px] w-[210px] rounded-full" />
        </div>
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1.45fr_1fr]">
        <div className="card space-y-5 p-7">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i}>
              <div className="skeleton h-3.5 w-40 rounded-full" />
              <div className="skeleton mt-2 h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
        <div className="card p-7">
          <div className="skeleton h-4 w-32 rounded-full" />
          <div className="skeleton mt-3 h-3 w-full rounded-full" />
          <div className="skeleton mt-2 h-3 w-4/5 rounded-full" />
          <div className="skeleton mt-4 h-10 w-56 rounded-xl" />
        </div>
      </div>
    </div>
  );
}
