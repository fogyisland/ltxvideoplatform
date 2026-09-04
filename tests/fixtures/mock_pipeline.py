class MockPipeline:
    def __init__(self, model_id: str = "mock"):
        self.model_id = model_id
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        # Return a 2-frame "video" as a list of PIL images
        from PIL import Image
        return [Image.new("RGB", (8, 8), (i * 50, 0, 0)) for i in range(2)]

    def to(self, device):
        return self