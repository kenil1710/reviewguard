# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }
import genlayer as gl
from genlayer import *

import json


class WaitProbe(gl.contract.Contract):
	out: str

	def __init__(self):
		self.out = ""

	@gl.public.write
	def measure(self, url: str, wait: str) -> None:
		"""Does a LONGER wait make Amazon render its reviews?

		The reviews sit below the fold and are fetched after load. Three live
		checks at 6s saw the rating summary and zero individual reviews, while
		probes an hour earlier at 5s saw eight. This isolates the one variable
		that is under the contract's control."""
		target = str(url)
		hold = str(wait)

		def leader_fn() -> dict:
			try:
				txt = gl.nondet.web.render(target, mode="text",
					wait_after_loaded=hold)
				if not isinstance(txt, str):
					txt = str(txt)
			except Exception as e:
				return {"ok": False, "err": str(e)[:200], "wait": hold}
			low = txt.lower()
			return {
				"ok": True, "wait": hold, "len": len(txt),
				"top_reviews_at": txt.find("Top reviews from"),
				"customer_reviews_at": txt.find("Customer reviews"),
				"verified": low.count("verified purchase"),
				"reviewed_on": low.count("reviewed in the"),
				"helpful": low.count("found this helpful"),
				"images": low.count("reviews with images"),
				"tail": txt[-260:],
			}

		def validator_fn(leader_result) -> bool:
			return isinstance(leader_result, gl.vm.Return)

		self.out = json.dumps(gl.vm.run_nondet(leader_fn, validator_fn))

	@gl.public.view
	def read(self) -> str:
		return self.out
