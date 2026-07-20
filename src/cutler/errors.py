from cutler.context import Ctx
from cutler.data import Job

class JobError(Exception):
    """An error that fails a single job.

    `short` is a concise, one-line description that is logged to stderr.
    `long` is optional detailed text (e.g. a failed command's stdout/stderr)
    that is written to a `{output_filename}.fail` file.
    """

    def __init__(self, short: str, long: str | None = None):
        super().__init__(short)
        self.short = short
        self.long = long

def handle_job_error(ctx: Ctx, job: Job, err: JobError):
    if err.long is None:
        ctx.display.log(err.short)
        return

    fail_path = f"{job.out_filename}.fail"
    try:
        with open(fail_path, "w") as f:
            f.write(err.long)
    except OSError:
        ctx.display.log(err.short)
        ctx.display.log(f"could not write {fail_path}")
        return

    ctx.display.log(f"{err.short}; wrote {fail_path}")
